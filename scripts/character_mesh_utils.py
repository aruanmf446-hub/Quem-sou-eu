"""Build original, skinned character assets. Run: blender -b -t 2 --python scripts/build-character-assets.py"""
import bpy, math
from mathutils import Vector
def mat(name,hex,rough=.65,metal=0):
 m=bpy.data.materials.new(name); m.diffuse_color=(*tuple(((int(hex[i:i+2],16)/255+.055)/1.055)**2.4 if int(hex[i:i+2],16)/255>.04045 else int(hex[i:i+2],16)/255/12.92 for i in (0,2,4)),1); m.use_nodes=True
 bs=m.node_tree.nodes.get('Principled BSDF'); bs.inputs['Base Color'].default_value=m.diffuse_color; bs.inputs['Roughness'].default_value=rough; bs.inputs['Metallic'].default_value=metal
 return m

def ell(name,loc,scale,material,bone=None,segments=24,rings=16):
 bpy.ops.mesh.primitive_uv_sphere_add(segments=segments,ring_count=rings,location=loc); o=bpy.context.object; o.name=name; o.scale=scale; bpy.ops.object.transform_apply(location=False,rotation=False,scale=True)
 o.data.materials.append(material)
 for p in o.data.polygons:p.use_smooth=True
 if bone:o['joint']=bone
 return o

def tube(name,points,radius,material,bone=None,cyclic=False):
 c=bpy.data.curves.new(name,'CURVE'); c.dimensions='3D'; c.resolution_u=12; c.bevel_depth=radius;c.bevel_resolution=3
 s=c.splines.new('BEZIER');s.bezier_points.add(len(points)-1)
 for p,co in zip(s.bezier_points,points):p.co=co;p.handle_left_type='AUTO';p.handle_right_type='AUTO'
 s.use_cyclic_u=cyclic;o=bpy.data.objects.new(name,c);bpy.context.collection.objects.link(o);o.data.materials.append(material)
 if bone:o['joint']=bone
 bpy.context.view_layer.objects.active=o;o.select_set(True);bpy.ops.object.convert(target='MESH');o.select_set(False)
 return o

def between(name,a,b,radius,material,bone,wide=1):
 a,b=Vector(a),Vector(b); mid=(a+b)/2;o=ell(name,mid,(radius,radius*wide,(b-a).length/2+radius*.25),material,bone)
 o.rotation_euler=(b-a).to_track_quat('Z','Y').to_euler();return o

def loft(name,sections,material,bone,n=40):
 # section: z, x radius, y radius, y offset. Smooth tailored silhouettes, not primitives.
 verts=[]
 for z,rx,ry,dy in sections:
  for i in range(n):
   a=2*math.pi*i/n;verts.append((math.cos(a)*rx,dy+math.sin(a)*ry,z))
 faces=[]
 for j in range(len(sections)-1):
  for i in range(n): faces.append((j*n+i,j*n+(i+1)%n,(j+1)*n+(i+1)%n,(j+1)*n+i))
 faces.extend([tuple(range(n-1,-1,-1)),tuple((len(sections)-1)*n+i for i in range(n))])
 mesh=bpy.data.meshes.new(name);mesh.from_pydata(verts,[],faces);mesh.update();o=bpy.data.objects.new(name,mesh);bpy.context.collection.objects.link(o);o.data.materials.append(material);o['joint']=bone
 for p in mesh.polygons:p.use_smooth=True
 mod=o.modifiers.new('Tailoring','SUBSURF');mod.levels=1
 bpy.context.view_layer.objects.active=o;o.select_set(True);bpy.ops.object.modifier_apply(modifier=mod.name);o.select_set(False);return o

def text(name,body,loc,size,material,bone):
 c=bpy.data.curves.new(name,'FONT');c.body=body;c.align_x='CENTER';c.size=size;c.extrude=.0006;c.bevel_depth=.0002
 o=bpy.data.objects.new(name,c);bpy.context.collection.objects.link(o);o.location=loc;o.rotation_euler=(math.pi/2,0,0);o.data.materials.append(material);o['joint']=bone
 bpy.context.view_layer.objects.active=o;o.select_set(True);bpy.ops.object.convert(target='MESH');o.select_set(False);return o

