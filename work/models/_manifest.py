import hashlib, json, os, time, importlib.metadata as M
root='work/models'; files=[]
for d,_,fs in os.walk(root):
    if '.cache' in d: continue
    for f in fs:
        if f in ('pip_constraints.txt','_manifest.py'): continue
        p=os.path.join(d,f).replace(os.sep,'/')
        h=hashlib.sha256()
        with open(p,'rb') as fh:
            for b in iter(lambda: fh.read(1<<24), b''): h.update(b)
        files.append({'path':p,'bytes':os.path.getsize(p),'sha256':h.hexdigest()})
man={'generated':time.strftime('%Y-%m-%d %H:%M'),'purpose':'HD level E generative pilot (docs/HD_BEYOND_D_PLAN.md); approved by Integration 2026-10-12/13',
 'models':[
  {'name':'Stable Diffusion v1.5 (fp16 components: unet, vae, text_encoder, tokenizer, scheduler)','source':'https://huggingface.co/stable-diffusion-v1-5/stable-diffusion-v1-5',
   'dir':'work/models/sd15','licence':'CreativeML OpenRAIL-M','licence_text':'work/models/licences/creativeml-openrail-m/license.txt',
   'note':'use restrictions (Attachment A) must be passed on with the pack credits; safety_checker not downloaded (textures, no people)'},
  {'name':'ControlNet v1.1 tile (control_v11f1e_sd15_tile)','source':'https://huggingface.co/lllyasviel/control_v11f1e_sd15_tile','dir':'work/models/controlnet_tile_sd15',
   'licence':'CreativeML OpenRAIL-M (model card: openrail)','licence_text':'work/models/licences/creativeml-openrail-m/license.txt',
   'note':'weights only in .bin (pickle); load with torch.load weights_only'}],
 'not_used':{'FLUX.1-schnell':'Apache-2.0 and preferred, but 12B parameters (about 24 GB fp16 transformer + T5-XXL) do not fit DirectML on the 24 GB RX 7900 XTX without quantised kernels, which DML lacks'},
 'python_packages':{p:M.version(p) for p in ('diffusers','transformers','accelerate','huggingface-hub','tokenizers','sentencepiece','protobuf','torch','torch-directml','numpy')},
 'pip_constraints':'work/models/pip_constraints.txt (torch / numpy / pillow / safetensors pinned; newest diffusers needs a newer torch than torch-directml supports, so diffusers 0.31 / transformers 4.46 / accelerate 1.1)',
 'files':files}
json.dump(man,open('manifests/hd/e_models.json','w',encoding='utf-8'),indent=1)
print(len(files),'files', round(sum(f['bytes'] for f in files)/2**30,2),'GB')
for f in files:
    if f['bytes']>10**7: print(f['path'],f['bytes'],f['sha256'][:16])
