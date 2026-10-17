"""Original character designs over the CC0 MakeHuman base. blender -b -t 3 --python scripts/build-character-assets.py"""
import bpy,math,json,os,sys,random
from mathutils import Vector
sys.path.insert(0,os.path.dirname(__file__))
from character_mesh_utils import mat,ell,tube,text,between,loft
ROOT=os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
ASSETS=os.path.join(ROOT,'scripts','assets'); OUT=os.path.join(ROOT,'public','models'); PREVIEW=os.path.join(ROOT,'work','renders')
os.makedirs(PREVIEW,exist_ok=True)
random.seed(42)

def load_source():
 verts=[];groups={};group='body';faces=[]
 for line in open(os.path.join(ASSETS,'human-base.obj')):
  if line.startswith('v '):verts.append(Vector(map(float,line.split()[1:])))
  elif line.startswith('g '):group=line.split()[1]
  elif line.startswith('f '):
   f=[int(x.split('/')[0])-1 for x in line.split()[1:]];groups.setdefault(group,[]).append(f)
 for filename,weight in [('male-young.target',.85),('athletic.target',.8)]:
  for line in open(os.path.join(ASSETS,filename)):
   if line.startswith('#') or not line.strip():continue
   a=line.split();i=int(a[0]);verts[i]+=Vector(map(float,a[1:]))*weight
 # Convert anatomical Y-up mesh to Blender Z-up. Slightly enlarge the head for game styling.
 def convert(v):
  x,y,z=v;h=(y+8.1676)*.12125
  p=Vector((x*.12125,-z*.12125,h))
  if h>1.72:
   w=min(1,(h-1.72)/.10);p.x*=1+.10*w;p.y*=1+.10*w;p.z=1.72+(h-1.72)*(1+.10*w)
  if h<1.07:p.x*=.84
  elif h<1.62:p.x*=1.08
  return p
 verts=[convert(v) for v in verts]
 def joint(name):
  ids=set(i for f in groups[name] for i in f);return sum((verts[i] for i in ids),Vector())/len(ids)
 weights=json.load(open(os.path.join(ASSETS,'body-weights.json')))['weights'];vw={}
 def remap(name):
  side=name[-2:]
  if name.startswith('upperarm'):return 'upper_arm'+side
  if name.startswith('lowerarm'):return 'forearm'+side
  if name.startswith(('finger','metacarpal','wrist')):return 'hand'+side
  if name.startswith('upperleg'):return 'thigh'+side
  if name.startswith('lowerleg'):return 'shin'+side
  if name.startswith(('foot','toe')):return 'foot'+side
  if name.startswith(('pelvis','root')):return 'hips'
  if name.startswith('spine'):return 'chest' if name in ['spine01','spine02'] else 'spine'
  if name.startswith(('breast','clavicle','shoulder')):return 'chest'
  if name.startswith('neck'):return 'neck'
  return 'head'
 for bn,pairs in weights.items():
  bone=remap(bn)
  for index,weight in pairs:
   d=vw.setdefault(index,{});d[bone]=d.get(bone,0)+weight
 return verts,groups['body'],joint,vw

VERTS,FACES,JOINT,VW=load_source()

def create_rig():
 bpy.ops.object.armature_add();rig=bpy.context.object;rig.name='CharacterRig';bpy.ops.object.mode_set(mode='EDIT');rig.data.edit_bones.remove(rig.data.edit_bones[0])
 pelvis=JOINT('joint-pelvis');neck=JOINT('joint-neck');head=JOINT('joint-head')
 joints={'hips':(pelvis,JOINT('joint-spine-4'),None),'spine':(JOINT('joint-spine-4'),JOINT('joint-spine-2'),'hips'),'chest':(JOINT('joint-spine-2'),neck,'spine'),'neck':(neck,head,'chest'),'head':(head,JOINT('joint-head-2'),'neck')}
 for side,source in [('L','r'),('R','l')]:
  shoulder=JOINT('joint-'+source+'-shoulder');elbow=JOINT('joint-'+source+'-elbow');wrist=JOINT('joint-'+source+'-hand');hand=JOINT('joint-'+source+'-hand-2');hip=JOINT('joint-'+source+'-upper-leg');knee=JOINT('joint-'+source+'-knee');ankle=JOINT('joint-'+source+'-ankle')
  joints.update({f'upper_arm.{side}':(shoulder,elbow,'chest'),f'forearm.{side}':(elbow,wrist,f'upper_arm.{side}'),f'hand.{side}':(wrist,hand,f'forearm.{side}'),f'thigh.{side}':(hip,knee,'hips'),f'shin.{side}':(knee,ankle,f'thigh.{side}'),f'foot.{side}':(ankle,ankle+Vector((0,-.17,-.02)),f'shin.{side}')})
 for name,(a,b,parent) in joints.items():
  bone=rig.data.edit_bones.new(name);bone.head=a;bone.tail=b
  if parent:bone.parent=rig.data.edit_bones[parent]
 bpy.ops.object.mode_set(mode='OBJECT');rig.select_set(False);return rig

def mesh_from_body(name,material,predicate,inflate=0,region='skin'):
 chosen=[f for f in FACES if predicate(sum((VERTS[i] for i in f),Vector())/len(f))];ids=sorted(set(i for f in chosen for i in f));remap={idx:i for i,idx in enumerate(ids)}
 mesh=bpy.data.meshes.new(name);mesh.from_pydata([VERTS[i] for i in ids],[],[[remap[i] for i in f] for f in chosen]);mesh.update()
 o=bpy.data.objects.new(name,mesh);bpy.context.collection.objects.link(o);o.data.materials.append(material)
 # Map handedness: source positive X is labeled L, ours positive X is R.
 for orig,new in remap.items():
  for bn,w in VW.get(orig,{'hips':1}).items():
   if bn.endswith('.L'):bn=bn[:-2]+'.R'
   elif bn.endswith('.R'):bn=bn[:-2]+'.L'
   (o.vertex_groups.get(bn) or o.vertex_groups.new(name=bn)).add([new],w,'ADD')
 if inflate:
  for v in mesh.vertices:v.co+=v.normal*inflate
 for p in mesh.polygons:p.use_smooth=True
 if region!='skin':
  solid=o.modifiers.new('Fabric thickness','SOLIDIFY');solid.thickness=.004
 sub=o.modifiers.new('Surface finish','SUBSURF');sub.levels=1
 bpy.context.view_layer.objects.active=o;o.select_set(True)
 for mod in list(o.modifiers):bpy.ops.object.modifier_apply(modifier=mod.name)
 o.select_set(False);o['weighted']=True;return o

def build(kind):
 bpy.ops.object.select_all(action='SELECT');bpy.ops.object.delete(use_global=False)
 football=kind=='striker';clown=kind=='night-clown';street=kind=='street'
 skin=mat('Skin','ac7653' if not clown else 'e0d8c9',.62);dark=mat('Ink','101724');white=mat('Ivory','e8e5da',.63)
 cloth=mat('OutfitPrimary','8463df' if street else 'efc51d' if football else 'c2b9a4',.86)
 pants=mat('OutfitSecondary','192634' if street else '0f386e' if football else '323239',.85)
 accent=mat('Accent','bcff62' if street else '13673c' if football else '8e1125',.64)
 hair=mat('Hair','18171c' if street else '65421e' if football else 'ae431b',.87)
 iris=mat('Iris','28271b' if not clown else 'ab7422',.28);lip=mat('Lips','754f46' if not clown else '7b1221',.65)
 metal=mat('Metal','697983',.3,.8)
 body=mesh_from_body('Anatomical body',skin,lambda p:(p.z>1.81 or (abs(p.x)<.083 and p.z>1.73)) or (abs(p.x)>.335 and p.z>.95) or (football and .11<p.z<.72))
 # A secondary material on real lip topology, preserving its sculpted volume.
 body.data.materials.append(lip)
 mouth=JOINT('joint-mouth');mouth.z=JOINT('joint-l-eye').z-.095;mouth.y=-.18
 for poly in body.data.polygons:
  p=poly.center
  if abs(p.x)<.036 and abs(p.z-mouth.z)<.014 and p.y<mouth.y-.018:poly.material_index=1
 # Garments are actual fitted surfaces derived from the anatomy, with smooth skin weights.
 shirt=loft('Tailored jersey' if football else 'Tailored jacket' if street else 'Victorian tunic',[(1.11,.207,.112,-.005),(1.17,.203,.117,-.01),(1.32,.165,.10,-.012),(1.50,.205,.135,-.014),(1.63,.25,.122,-.015),(1.69,.238,.10,-.015),(1.74,.115,.074,-.012),(1.77,.074,.065,-.01)],cloth,'spine')
 # Project face paint, eyebrows and seams onto the actual anatomical surface.
 def front(x,z):
  points=[v for v in VERTS if abs(v.x-x)<.014 and abs(v.z-z)<.014 and v.z>1.80]
  return min((v.y for v in points),default=-.18)-.004
 trousers=mesh_from_body('Athletic shorts' if football else 'Trousers',pants,lambda p:(.70 if football else .13)<p.z<1.07 and abs(p.x)<.335,.022 if football else .016,'cloth')
 if football:
  for side,source in [('L','r'),('R','l')]:
   x=JOINT('joint-'+source+'-ankle').x
   mesh_from_body('Football sock '+side,white,lambda p,x=x:.105<p.z<.50 and p.x*x>0,.006,'cloth')
 loft('Waistband',[(.98,.215,.115,-.012),(1.035,.25,.14,-.012),(1.10,.23,.13,-.012),(1.16,.207,.12,-.012)],pants,'hips')
 # Eyes and brows use anatomical attachment centers.
 for side,source in [('L','r'),('R','l')]:
  e=JOINT('joint-'+source+'-eye');x,y,z=e
  ell('Eyeball',e,(.0215,.0215,.0215),white,'head',32,20)
  ell('Iris',(x,y-.0208,z),(.009,.002,.009),iris,'head',24,16)
  ell('Pupil',(x,y-.0225,z),(.004,.001,.0048),dark,'head')
  ell('Catchlight',(x-.0025,y-.0234,z+.003),(.0018,.001,.0018),white,'head',12,8)
  s=1 if x>0 else -1
  tube('Eyebrow',[(x-s*.023,front(x-s*.023,z+.031),z+.031),(x,front(x,z+.037),z+.037),(x+s*.025,front(x+s*.025,z+.028),z+.028)],.005,dark if clown else hair,'head')
  if clown:
   tube('Eye paint',[(px,front(px,pz)-.002,pz) for px,pz in [(x-s*.008,z+.09),(x,z+.038),(x,z-.028),(x+s*.015,z-.075)]],.004,accent,'head')
 # Hair follows the scalp. Swept tapered locks create a coherent sculpted silhouette.
 top=max(v.z for v in VERTS);head=JOINT('joint-head');hz=top-.025
 if not clown:
  mesh_from_body('Fitted haircut',hair,lambda p:p.z>(2.055 if p.y<-.09 else 2.005),.007)
  ell('Hair silhouette',(0,-.056,hz-.036),(.112,.119,.056),hair,'head',40,24)
  for i in range(40):
   a=i*2.39996;r=.09*math.sqrt((i+.5)/40);x=math.cos(a)*r;y=math.sin(a)*r*.95-.056
   tube('Swept hair lock',[(x,y,hz-.012),(x+.018,y+.018,hz+.026),(x+.04,y+.035,hz+.028)],.013*(1-.35*r/.09),hair,'head')
  # Thin beard follows the jaw, subtle rather than a disconnected rounded patch.
  for s in [-1,1]:
   tube('Jaw shadow',[(s*.080,-.05,head.z+.018),(s*.077,-.071,head.z-.014),(s*.047,-.094,head.z-.042),(0,-.103,head.z-.048)],.0035,hair,'head')
 else:
  for s in [-1,1]:
   for i in range(32):
    f=i/31; angle=i*2.4; dx=.014*math.cos(angle);dy=.035*math.sin(angle)
    tube('Swept temple hair',[(s*(.105+dx),-.025+dy,hz-.11+f*.06),(s*(.15+dx),-.005+dy*.8,hz-.05+f*.035),(s*(.18+dx),.03+dy*.5,hz+.015+f*.035)],.012,hair,'head')
  # A larger pointed painted smile on the existing facial mesh.
  for s in [-1,1]:tube('Painted smile',[(px,front(px,pz)-.002,pz) for px,pz in [(0,mouth.z),(s*.036,mouth.z+.003),(s*.06,mouth.z+.034)]],.0045,accent,'head')
  ell('Painted nose',(0,front(0,JOINT('joint-l-eye').z-.055)-.003,JOINT('joint-l-eye').z-.055),(.017,.01,.013),accent,'head')
 # Deliberate costume construction: neck binding, seams, badges and hardware.
 neck=JOINT('joint-neck')
 if clown:
  for i in range(28):
   a=i*math.tau/28;o=ell('Pleated ruff',(.09*math.cos(a),.075*math.sin(a),neck.z-.014),(.025,.025,.018),white,'neck');o.rotation_euler[2]=a
  for z in [1.30,1.46,1.61]:ell('Pompom',(0,-.15,z),(.025,.022,.025),accent,'spine')
  for s in [-1,1]:tube('Tunic piping',[(s*.10,-.11,1.16),(s*.13,-.125,1.43),(s*.15,-.12,1.66)],.0035,accent,'spine')
 elif football:
  text('Number','10',(0,-.151,1.36),.13,pants,'spine');text('Team mark','CRAQUE',(0,-.155,1.55),.028,pants,'chest')
  ell('Crest',(-.10,-.138,1.59),(.019,.004,.025),accent,'chest')
  for s in [-1,1]:tube('Side panel',[(s*.13,-.02,1.14),(s*.17,-.025,1.40),(s*.20,-.015,1.59)],.007,accent,'spine')
 else:
  tube('Jacket zip',[(0,-.12,1.13),(0,-.125,1.32),(0,-.155,1.50),(0,-.095,1.73)],.003,metal,'spine')
  for s in [-1,1]:
   tube('Jacket seam',[(s*.11,-.08,1.15),(s*.13,-.10,1.35),(s*.17,-.08,1.52)],.004,accent,'spine')
   tube('Pocket zip',[(s*.035,-.107,1.25),(s*.11,-.086,1.21)],.0025,metal,'spine')
  text('Streetwear logo','Q / E',(-.10,-.14,1.59),.024,white,'chest')
 # Cuffs, shoes, laces and tattoos are attached to the same weighted skeleton.
 for side,source in [('L','r'),('R','l')]:
  s=-1 if side=='L' else 1
  shoulder=JOINT('joint-'+source+'-shoulder');elbow=JOINT('joint-'+source+'-elbow');wrist=JOINT('joint-'+source+'-hand')
  sleeve_end=shoulder.lerp(elbow,.67 if football else 1.02)
  delta=sleeve_end-shoulder;L=delta.length
  sleeve=loft('Tailored sleeve',[(0,.082,.073,0),(L*.12,.087,.078,0),(L*.8,.073,.068,0),(L,.068,.064,0)],cloth,'upper_arm.'+side)
  sleeve.location=shoulder;sleeve.rotation_euler=delta.to_track_quat('Z','Y').to_euler()
  if not football:between('Forearm fabric',elbow,wrist,.065,cloth,'forearm.'+side,.9)
  band=sleeve_end.lerp(shoulder,.06);between('Sleeve binding',band,sleeve_end,.069,accent,'upper_arm.'+side,.92)
  ankle=JOINT('joint-'+source+'-ankle');x=ankle.x
  foot='foot.'+side; forearm='forearm.'+side
  shoeMat=dark if street else accent if football else pants
  ell('Shoe sole',(x,-.075,.037),(.076,.16,.027),white if not clown else dark,foot)
  ell('Structured sneaker',(x,-.065,.083),(.073,.15,.058),shoeMat,foot)
  ell('Padded tongue',(x,-.047,.113),(.034,.058,.015),cloth,foot)
  for i in range(5):tube('Laces',[(x-.025,-.02-i*.018,.123-i*.002),(x+.025,-.025-i*.018,.123-i*.002)],.0025,white,foot)
  if clown:ell('Pointed toe',(x,-.175,.052),(.057,.09,.03),accent,foot)
  else:tube('Shoe trim',[(x+s*.064,-.125,.060),(x+s*.068,-.06,.084),(x+s*.059,-.01,.086)],.004,accent if street else pants,foot)
  if football:
   knee=JOINT('joint-'+source+'-knee');b=knee.lerp(ankle,(knee.z-.49)/(knee.z-ankle.z));between('Sock cuff',b,b+Vector((0,0,.025)),.067,accent,'shin.'+side)
   elbow=JOINT('joint-'+source+'-elbow');wrist=JOINT('joint-'+source+'-hand')
   for i in range(8):
    p=elbow.lerp(wrist,.25+i*.065);tube('Ink line',[(p.x-.015,p.y-.037,p.z+.008),(p.x+.005,p.y-.042,p.z-.008),(p.x+.017,p.y-.03,p.z+.003)],.0013,dark,forearm)
 rig=create_rig()
 for o in list(bpy.context.scene.objects):
  if o.type!='MESH':continue
  if 'joint' in o:
   if o['joint']=='spine':
    for v in o.data.vertices:
     z=(o.matrix_world@v.co).z;w=max(0,min(1,(z-1.40)/.27))
     for bn,weight in [('spine',1-w),('chest',w)]:
      if weight>0:(o.vertex_groups.get(bn) or o.vertex_groups.new(name=bn)).add([v.index],weight,'REPLACE')
   else:
    group=o.vertex_groups.new(name=o['joint']);group.add(list(range(len(o.data.vertices))),1,'REPLACE')
  mod=o.modifiers.new('Skin','ARMATURE');mod.object=rig;o.parent=rig
 # Join preserving normals, material slots and all skin weights; one skinned mesh.
 bpy.ops.object.select_all(action='DESELECT');meshes=[o for o in bpy.context.scene.objects if o.type=='MESH']
 for o in meshes:o.select_set(True)
 bpy.context.view_layer.objects.active=meshes[0];bpy.ops.object.join();body=meshes[0];body.name=kind+'-skinned-mesh'
 dec=body.modifiers.new('Delivery topology','DECIMATE');dec.ratio=.55;bpy.context.view_layer.objects.active=body;bpy.ops.object.modifier_apply(modifier=dec.name)
 bpy.ops.object.select_all(action='DESELECT');body.select_set(True);rig.select_set(True)
 bpy.ops.export_scene.gltf(filepath=os.path.join(OUT,kind+'.glb'),export_format='GLB',use_selection=True,export_animations=False,export_yup=True,export_skins=True)
 rig.rotation_euler[2]=math.radians(-10)
 scene=bpy.context.scene;scene.render.engine='CYCLES';scene.cycles.samples=48;scene.cycles.use_denoising=False
 scene.render.resolution_x=600;scene.render.resolution_y=800;scene.render.resolution_percentage=100;scene.render.image_settings.file_format='PNG';scene.render.film_transparent=True
 scene.world.color=(.18,.18,.18)
 def light(loc,power,color,size):
  bpy.ops.object.light_add(type='AREA',location=loc);o=bpy.context.object;o.data.energy=power;o.data.color=color;o.data.shape='DISK';o.data.size=size;o.rotation_euler=(Vector((0,0,1.2))-o.location).to_track_quat('-Z','Y').to_euler()
 light((2,-4,5),450,(.9,.95,1),4);light((-2,2,3),650,(.6,.5,1),3);light((-3,-2,2),180,(.5,.8,1),3)
 bpy.ops.object.camera_add(location=(2.1,-6,2.5));cam=bpy.context.object;cam.rotation_euler=(Vector((0,0,1.10))-cam.location).to_track_quat('-Z','Y').to_euler();cam.data.type='ORTHO';cam.data.ortho_scale=2.40;scene.camera=cam
 scene.view_settings.view_transform='AgX';scene.render.filepath=os.path.join(PREVIEW,kind+'.png');bpy.ops.render.render(write_still=True)
 bpy.ops.wm.save_as_mainfile(filepath=os.path.join(ROOT,'work',kind+'.blend'))
for kind in ['striker','night-clown','street']:build(kind)
print('ASSETS COMPLETE')
