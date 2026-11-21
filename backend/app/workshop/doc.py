# backend/app/workshop/doc.py
"""SPEC_DOC: the LLM-facing description of the part-tree spec (used verbatim in tool descriptions and prompts)."""

SPEC_DOC = """\
PART TREE SPEC (JSON, no code). Describe a physical object as data; the server validates and builds it.
{"name":str, "units":"mm"|"cm"|"m" (default mm), "params":{...}, "parts":[{"id":..,"kind":..,...}]}
Axes: x right, y UP, z toward the viewer. Ground the object: lowest point at y=0, centre parts by pos.
Real-world proportions and units; prefer 20..150 parts; name ids meaningfully (seat, leg, blade).

PARAMS: name -> number or {"value":n,"min":n,"max":n,"step":n,"label":str,"unit":str}. Max 40. Make the
dimensions the user may change parameters (min defaults to value/10, max to value*5).
EXPRESSIONS: any number may be a string "=expr" using + - * / ^ % ( ), params, pi and min max abs sqrt sin cos
tan atan2 clamp(x,lo,hi) round floor ceil (radians). Example "=width*0.5-10". Unknown names are errors.

KINDS (sizes are full sizes, not half sizes):
 box{size:[x,y,z]}  sphere{r}  cylinder{r,h} or {r1,r2,h} (r1 or r2 = 0 gives a cone; two radii: cylinder of the
 mean radius)  capsule{r,h} (h = total height >= 2r)  torus{r,tube} (ring in the xz plane, tube ~ 0.3*r)
 plane{size:[x,z]} (horizontal)  extrude{outline:[[x,z],..3..64 points],h} (prism standing on its pos)
 lathe{profile:[[r,y],..2..64 points, r>=0],segments:24} (turned around the y axis: vase, bottle, bowl, hub)
 polyline{pts:[[x,y,z],..],width,closed}  label{text,size}  group{} (container).
COMMON: id (letters, digits, _ -), kind, name, pos:[x,y,z], rot:[rx,ry,rz] in DEGREES, color (CSS), material:{metal,
 rough,opacity: 0..1}, parent (id of a group; the child is positioned relative to the group), tags:[..] (first tag =
 layer).
SYMMETRY: "mirror":"x"|"y"|"z" adds a mirrored copy across that plane through the group origin (id "<id>.m").
 For a left/right pair put the part at +x and add "mirror":"x".
REPETITION: "array":{"type":"linear","count":n,"step":[x,y,z]} or {"type":"radial","count":n,"axis":"x|y|z",
 "radius":r,"start_deg":a} (count <= 200; members "<id>.0", "<id>.1"; with mirror also "<id>.0.m").
 Radial: the part's pos is offset by radius, then the member is turned about the axis through the parent origin.
 Groups can be mirrored and arrayed with all their children. Use mirror and array, never copy parts by hand.
LIMITS: 2000 parts after expansion, group depth 6. Any error names the field path; fix it and send the spec again.

EXAMPLE 1 (stool with a parameter):
{"units":"mm","params":{"h":{"value":450,"min":300,"max":700,"label":"Height"}},"parts":[
 {"id":"seat","kind":"cylinder","r":160,"h":30,"pos":[0,"=h-15",0]},
 {"id":"leg","kind":"cylinder","r":15,"h":"=h-30","pos":[90,"=(h-30)/2",0],
  "array":{"type":"radial","count":3,"axis":"y","start_deg":0}}]}
EXAMPLE 2 (mirrored pair under a group):
{"parts":[{"id":"torso","kind":"box","size":[300,350,180],"pos":[0,550,0]},
 {"id":"arm","kind":"group","pos":[200,650,0],"mirror":"x"},
 {"id":"upper","kind":"capsule","r":25,"h":200,"parent":"arm","pos":[0,-100,0]}]}
"""
