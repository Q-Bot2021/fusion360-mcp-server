# Image Stencil Reconstruction

The user authorized three individual new designs in `MCP_Dev`, excluding the
crossed-out ellipse template. The source was an attached low-resolution image,
not dimensioned CAD. Overall dimensions, some aperture labels and positions are
estimated. Saved design names include `Approx`; these are not certified copies
of the photographed measuring instruments.

| Design | Estimated Plate Size (mm) | Apertures | Ruler |
| --- | --- | --- | --- |
| Circles_Small | 105 x 200 | 22 circles, nominal diameter 3-40 mm | 0-18 cm, 1 mm divisions |
| Circles_Large | 132 x 220 | 7 circles, nominal diameter 38-60 mm | 0-21 cm, 1 mm divisions |
| Mixed_Shapes | 110 x 220 | 15 circles, 15 squares, 12 hexagons, 12 triangles | 0-20 cm, 1 mm divisions |

The two circle templates include full-circle protractors with 5-degree ticks
and 30-degree numerical labels. Aperture annotations include millimetre units.
Hexagon sizes are across flats (`AF`); equilateral triangle sizes are side
lengths (`S`). Square annotations specify side length. Nominal dimensions are
at the bottom tracing opening; internal chamfers enlarge only the upper opening.

## User-Confirmed Manufacturing Interpretation

- Plate thickness: 2.5 mm, excluding no additional raised features.
- Text: recessed 0.01 mm, vertical square-sided walls, created as Fusion sketch
  text and cut directly without exploding the text or chamfering its edges.
- Scale ticks: recessed 0.01 mm into the flat top surface, 0.12 mm stroke width.
- Ruler side: full-height 30-degree internal angle, bottom footprint wider than
  the top, 4.330127 mm horizontal setback.
- Internal edges: matching 30-degree angle with 0.1 mm vertical depth and
  0.173205 mm horizontal setback, explicitly approved to preserve small holes.
- Annotations and ticks are on the top face, not printed underneath translucent
  stock. The model does not depend on transparent manufacturing material.

The reconstruction uses rectangular plate outlines. The image's rounded corners
and unreadable fine annotations are not exact reproductions. A 10-micrometre
engraving is deliberately shallow: model placement does not certify legibility
or manufacturing tolerance. Verify the chosen process and surface finish before
using the parts as precision measuring instruments.

## Development Tools and Evidence

`create_design`, `draw_sketch_text`, `extrude_sketch_entities`, and
`chamfer_stencil_edges` are isolated development candidates only. Production
discovery and execution policy remain unchanged. The fixed, hash-owned add-in
reload is used; no arbitrary code is sent to Fusion.

Unit/protocol checks are in `test_sandbox_documents.py` and
`test_development_registration.py`. Opt-in live acceptance is
`tests/test_sandbox_live.py::test_stencil_tools_live`. The live fixture verified
new-document creation, the 30-degree bevel normal, a shallow internal chamfer,
literal sketch text and successful 0.01 mm cut extrusion. It remains an unsaved
disposable document; it is not one of the three saved stencils.

The client workflow is `scripts/create_stencils.py`; unit checks are in
`tests/test_stencil_workflow.py`. It issues separate sequential MCP requests,
records every result, never deletes an existing design, stops on errors without
retrying mutations, and verifies feature health before saving. The complete
assumed layout is recorded in `.pytest_cache/stencil-build.json`, alongside
save identities, project readback and feature health. Live tool evidence is in
`.pytest_cache/stencil-tools-live.json`. These reports must be inspected before
claiming a completed build. Preserve failure evidence and inspect Fusion before
attempting any recovery.

Do not rerun the build casually: it creates new documents, and cloud save must
not be repeated after an ambiguous response. The reusable development add-in
installation is retained. Unsaved acceptance fixtures can be closed without
saving after evidence has been preserved; unrelated documents must be left open.