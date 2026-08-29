# Brand Assets

Werkblatt verwendet das freigegebene **Werkblatt Brand System 1.0.1**. Die geometrischen Master unter `source-master/` wurden nicht in dieses Repository übernommen und nicht verändert. Die folgenden Produktionsassets wurden am 28. August 2026 byte-identisch übernommen.

| Ziel | Rolle | SHA-256 |
|---|---|---|
| `static/werkblatt/brand/werkblatt-logo.svg` | Primärlogo hell | `c925f549e5d972e632b608140cca424752d540bd8dc8b63459145fa8b74cda04` |
| `static/werkblatt/brand/werkblatt-logo-inverted.svg` | Lockup auf dunklem Hintergrund | `7c6df5a840389abe5e7828dda2f885ea1ff71259cf5b7bc4b0cb4ce84a6120bc` |
| `static/werkblatt/brand/werkblatt-logo-claim.svg` | Primärlogo mit Claim für öffentliche Einstiege | `1eb71bdad5e9e8e8c3988c98ced1797dc638f90047b98192c732c202dfa2b781` |
| `static/werkblatt/brand/werkblatt-logo-claim-inverted.svg` | Claim-Lockup auf dunklem Hintergrund | `a6c1e9a11449550871f7628bf23ef87e7c661d4319335f6db42aa34fcf54ddf5` |
| `static/werkblatt/brand/werkblatt-mark-color.svg` | kompaktes Farbsignet | `8ad3d933a4e3c5a4f4930b7c01ff85218836f2e77a0f3bc344bedbf6916ffcf8` |
| `static/werkblatt/icons/*` | App, PWA, Maskable und Apple Touch | siehe Git-Historie/Dateihashes |
| `static/werkblatt/favicon/*` | Browser-Assets | siehe Git-Historie/Dateihashes |

Die CSS-Tokens in `static/werkblatt/css/tokens.css` sind aus `brand.json` abgeleitet. Logo-Geometrie, Farben, Negativräume, Proportionen und Lockups dürfen nicht über CSS oder Bildbearbeitung verändert werden.

Öffentliche beziehungsweise nicht eingeloggte Produkteinstiege verwenden das
freigegebene Claim-Lockup, sofern es mindestens 180 px breit und damit lesbar
dargestellt werden kann. Auf sehr schmalen Viewports wechselt die Oberfläche auf
das normale Primärlogo mit mindestens 140 px Breite. Die eingeloggte
Arbeitsoberfläche verwendet das kompaktere Primärlogo. Hell- und Dark-Mode nutzen
jeweils ausschließlich die dafür freigegebene Produktionsvariante; der Claim
wird nicht separat gesetzt.

## Inter

Inter Regular 400 und SemiBold 600 stammen aus der offiziellen Inter-4.1-Veröffentlichung von `rsms/inter`:

| Ziel | SHA-256 |
|---|---|
| `static/werkblatt/fonts/Inter-Regular.woff2` | `e06f6b1bc553aaea4e4668023ed0ab0a147129c3107f511bc7d03d361b0ae085` |
| `static/werkblatt/fonts/Inter-SemiBold.woff2` | `5cb7103e4e605989afebc03d989c79201e54b21b5183db33981f70db9178a301` |
| `licenses/Inter-OFL-1.1.txt` | `262481e844521b326f5ecd053e59b98c8b2da78c8ee1bdbb6e8174305e54935a` |

Inter steht unter der SIL Open Font License 1.1. Der vollständige mitgelieferte Lizenztext bleibt im Repository erhalten.
