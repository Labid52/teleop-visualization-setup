# Bundled MapLibre browser assets

Pinned MapLibre GL JS **5.6.1**, from the official `maplibre-gl` npm package:

- https://unpkg.com/maplibre-gl@5.6.1/dist/maplibre-gl.js
- https://unpkg.com/maplibre-gl@5.6.1/dist/maplibre-gl.css
- https://unpkg.com/maplibre-gl@5.6.1/LICENSE.txt

The license is included as `LICENSE-MapLibre.txt`. These source distribution
assets are committed so startup does not require fetching JavaScript from a CDN.
No secrets or runtime map captures are included.

SHA-256:

```text
b5a34e6930ff937dbbb9eec8892cffb80ba473cce88ae5ca8c4654432f5f0ebc  maplibre-gl.js
792ac997dcf6ae6f643eb4e2dee4630c85e7056526bd8fb85ffe83c67d6c41b4  maplibre-gl.css
ee5fc05a0677eaf69601d2c7db0d9ecd6cc27c3abc1d0733bc9ed34707cf8ef2  LICENSE-MapLibre.txt
```

The WAN map uses `https://tiles.openfreemap.org/styles/positron` with local
navigation-palette and numeric-filter adjustments in `navigation.js`. OpenFreeMap,
OpenMapTiles, and OpenStreetMap attribution is displayed by the map. See
https://openfreemap.org/quick_start/ and https://maplibre.org/maplibre-gl-js/docs/.
Offline demo geometry is fictional and contains no downloaded tiles.
