# Asset provenance

The vendored symbols, footprints and standard STEP models were copied from KiCad 10.0.6's installed standard libraries. Upstream homes:

- https://gitlab.com/kicad/libraries/kicad-symbols
- https://gitlab.com/kicad/libraries/kicad-footprints
- https://gitlab.com/kicad/libraries/kicad-packages3D
- https://www.kicad.org/libraries/license/

Their existing descriptions and model provenance comments are retained. Symbol definitions were flattened from standard inheritance, renamed into the Demo namespace, and U1's metadata was corrected to the pin-compatible LMV358A/SOIC-8 device. Footprint model links were localized to models/. D2's STEP diffuse body colour was changed from red to green; its dimensions and transforms are unchanged. These library derivatives retain CC-BY-SA-4.0 with the KiCad libraries exception; see LICENSE.KiCad.md.

CR2032_nominal.wrl is an original nominal cell envelope, not sourced from a manufacturer CAD file. It represents 20 mm diameter by 3.2 mm thickness; its position in the holder is illustrative. models/ contains geometry for every fitted electrical reference. The four unpopulated mounting holes have no component body. Standard models represent package envelopes, not exact supplier-qualified parts.
