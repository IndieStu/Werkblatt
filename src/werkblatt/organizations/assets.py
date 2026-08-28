import hashlib
import io
import re
import struct
import warnings
import xml.etree.ElementTree as ElementTree

from defusedxml import ElementTree as SafeElementTree
from django.core.exceptions import ValidationError
from django.core.files.base import ContentFile
from django.db import models, transaction
from PIL import Image, UnidentifiedImageError

from werkblatt.identities.models import Membership

from .models import BrandAsset, BrandAssetVersion

SVG_LIMIT = 2 * 1024 * 1024
PNG_LIMIT = 10 * 1024 * 1024
MAX_EDGE = 8000
MAX_PIXELS = 40_000_000
MAX_SVG_NODES = 10_000
MAX_SVG_DEPTH = 64
SVG_ELEMENTS = {
    "svg",
    "g",
    "path",
    "rect",
    "circle",
    "ellipse",
    "line",
    "polyline",
    "polygon",
    "defs",
    "linearGradient",
    "radialGradient",
    "stop",
    "clipPath",
    "mask",
    "title",
    "desc",
    "use",
}
SVG_ATTRIBUTES = {
    "viewBox",
    "width",
    "height",
    "x",
    "y",
    "x1",
    "y1",
    "x2",
    "y2",
    "cx",
    "cy",
    "r",
    "rx",
    "ry",
    "d",
    "points",
    "fill",
    "fill-opacity",
    "fill-rule",
    "stroke",
    "stroke-width",
    "stroke-linecap",
    "stroke-linejoin",
    "stroke-opacity",
    "opacity",
    "transform",
    "gradientUnits",
    "gradientTransform",
    "offset",
    "stop-color",
    "stop-opacity",
    "clip-path",
    "mask",
    "id",
    "href",
    "preserveAspectRatio",
}
UNSAFE_SVG = re.compile(
    rb"<\s*(script|foreignObject|animate|set)\b|\bon[a-z]+\s*=|<!DOCTYPE|<!ENTITY|"
    rb"(?:href|src)\s*=\s*['\"]\s*(?:https?:|file:|javascript:|data:|//)|@import|"
    rb"url\s*\(\s*['\"]?\s*(?:https?:|file:|javascript:|data:|//)|"
    rb"expression\s*\(|-moz-binding|behavior\s*:",
    re.IGNORECASE,
)


def _png_metadata_and_preview(content: bytes) -> tuple[int, int, bytes]:
    offset = 8
    found_iend = False
    while offset + 12 <= len(content):
        length = struct.unpack(">I", content[offset : offset + 4])[0]
        end = offset + 12 + length
        if end > len(content):
            raise ValidationError("Die PNG-Datei ist beschädigt oder unvollständig.")
        chunk_type = content[offset + 4 : offset + 8]
        offset = end
        if chunk_type == b"IEND":
            found_iend = True
            break
    if not found_iend or offset != len(content):
        raise ValidationError("Die PNG-Datei enthält unzulässige angehängte Daten.")
    try:
        with warnings.catch_warnings():
            warnings.simplefilter("error", Image.DecompressionBombWarning)
            with Image.open(io.BytesIO(content)) as image:
                image.verify()
            with Image.open(io.BytesIO(content)) as image:
                width, height = image.size
                if width > MAX_EDGE or height > MAX_EDGE or width * height > MAX_PIXELS:
                    raise ValidationError("Das Bild ist für Werkblatt zu groß.")
                image.load()
                preview = image.convert("RGBA")
                preview.thumbnail((1200, 1200))
                output = io.BytesIO()
                preview.save(output, format="PNG", optimize=True)
                return width, height, output.getvalue()
    except (Image.DecompressionBombError, Image.DecompressionBombWarning) as exc:
        raise ValidationError("Das Bild überschreitet das sichere Pixel-Limit.") from exc
    except (UnidentifiedImageError, OSError) as exc:
        raise ValidationError("Die PNG-Datei ist beschädigt oder ungültig.") from exc


def _svg_metadata_and_preview(content: bytes) -> tuple[int, int, bytes]:
    if UNSAFE_SVG.search(content):
        raise ValidationError("Das SVG enthält aktive oder externe Inhalte.")
    try:
        root = SafeElementTree.fromstring(content)
    except (ElementTree.ParseError, ValueError) as exc:
        raise ValidationError("Die SVG-Datei ist beschädigt oder ungültig.") from exc
    if root.tag.split("}")[-1].lower() != "svg":
        raise ValidationError("Die Datei enthält kein gültiges SVG.")
    nodes = 0
    stack = [(root, 1)]
    while stack:
        element, depth = stack.pop()
        nodes += 1
        if nodes > MAX_SVG_NODES or depth > MAX_SVG_DEPTH:
            raise ValidationError("Das SVG ist zu komplex.")
        tag = element.tag.split("}")[-1]
        if tag not in SVG_ELEMENTS:
            raise ValidationError("Das SVG enthält nicht erlaubte Elemente.")
        for raw_name, raw_value in element.attrib.items():
            name = raw_name.split("}")[-1]
            if name not in SVG_ATTRIBUTES:
                raise ValidationError("Das SVG enthält nicht erlaubte Attribute.")
            value = raw_value.strip()
            if name == "href" and not value.startswith("#"):
                raise ValidationError("Das SVG enthält aktive oder externe Inhalte.")
            if name in {"fill", "stroke", "clip-path", "mask"} and "url(" in value.lower():
                match = re.fullmatch(r"url\(\s*#[A-Za-z_][\w:.-]*\s*\)", value)
                if not match:
                    raise ValidationError("Das SVG enthält aktive oder externe Inhalte.")
        stack.extend((child, depth + 1) for child in list(element))
    view_box = root.attrib.get("viewBox", "").replace(",", " ").split()
    try:
        if len(view_box) == 4:
            width, height = round(float(view_box[2])), round(float(view_box[3]))
        else:
            width = round(float(re.sub(r"[^0-9.]", "", root.attrib.get("width", ""))))
            height = round(float(re.sub(r"[^0-9.]", "", root.attrib.get("height", ""))))
    except (TypeError, ValueError) as exc:
        raise ValidationError("Das SVG benötigt eine gültige ViewBox oder Abmessungen.") from exc
    if width <= 0 or height <= 0 or width > MAX_EDGE or height > MAX_EDGE:
        raise ValidationError("Die SVG-Abmessungen sind ungültig oder zu groß.")
    try:
        import cairosvg

        preview = cairosvg.svg2png(bytestring=content, output_width=min(width, 1200))
    except Exception as exc:
        raise ValidationError(
            "Für dieses SVG konnte keine sichere Vorschau erzeugt werden."
        ) from exc
    return width, height, preview


def validate_asset_upload(upload) -> tuple[str, bytes, int, int, bytes]:
    content = upload.read(max(PNG_LIMIT, SVG_LIMIT) + 1)
    is_png = content.startswith(b"\x89PNG\r\n\x1a\n")
    is_svg = content.lstrip().startswith(b"<") and b"<svg" in content[:2048].lower()
    if is_png:
        if len(content) > PNG_LIMIT:
            raise ValidationError("PNG-Dateien dürfen höchstens 10 MiB groß sein.")
        width, height, preview = _png_metadata_and_preview(content)
        return "image/png", content, width, height, preview
    if is_svg:
        if len(content) > SVG_LIMIT:
            raise ValidationError("SVG-Dateien dürfen höchstens 2 MiB groß sein.")
        width, height, preview = _svg_metadata_and_preview(content)
        return "image/svg+xml", content, width, height, preview
    raise ValidationError("Werkblatt unterstützt in V1 ausschließlich SVG und PNG.")


def _require_asset_admin(organization, user) -> None:
    if (
        not user.is_authenticated
        or not user.memberships.filter(
            organization=organization,
            role=Membership.Role.ORGANIZATION_ADMIN,
            status=Membership.Status.ACTIVE,
        ).exists()
    ):
        raise ValidationError("Nur Organization Admins dürfen Logos verwalten.")


@transaction.atomic
def create_asset(*, organization, user, display_name, default_role, upload) -> BrandAsset:
    _require_asset_admin(organization, user)
    asset = BrandAsset.objects.create(
        organization=organization,
        display_name=display_name.strip(),
        default_role=default_role,
        created_by=user,
        updated_by=user,
    )
    version = add_asset_version(asset=asset, organization=organization, user=user, upload=upload)
    asset.current_version = version
    return asset


@transaction.atomic
def add_asset_version(*, asset, organization, user, upload) -> BrandAssetVersion:
    _require_asset_admin(organization, user)
    if asset.organization_id != organization.id:
        raise ValidationError("Logo gehört nicht zu dieser Organisation.")
    caller_asset = asset
    asset = BrandAsset.objects.select_for_update().get(pk=asset.pk, organization=organization)
    media_type, content, width, height, preview = validate_asset_upload(upload)
    number = (asset.versions.aggregate(maximum=models.Max("number"))["maximum"] or 0) + 1
    version = BrandAssetVersion(
        organization=organization,
        asset=asset,
        number=number,
        original_filename=re.split(r"[/\\]", upload.name)[-1][:255],
        media_type=media_type,
        byte_size=len(content),
        width=width,
        height=height,
        sha256=hashlib.sha256(content).hexdigest(),
        created_by=user,
    )
    suffix = "svg" if media_type == "image/svg+xml" else "png"
    version.original_file.save(f"original.{suffix}", ContentFile(content), save=False)
    version.preview_file.save("preview.png", ContentFile(preview), save=False)
    version.save()
    asset.current_version = version
    asset.updated_by = user
    asset.save(update_fields=["current_version", "updated_by", "updated_at"])
    caller_asset.current_version = version
    return version
