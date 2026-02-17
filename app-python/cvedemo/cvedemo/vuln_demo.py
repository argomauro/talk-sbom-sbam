import yaml
import os

##VULNERABILITA' PILLOW
from django.shortcuts import render
from .forms import UploadForm
from PIL import Image # La libreria vulnerabile

def upload_avatar(request):
    if request.method == 'POST':
        form = UploadForm(request.POST, request.FILES)
        if form.is_valid():
            img_file = request.FILES['avatar']
            
            # Apertura dell'immagine per processing (punto di trigger)
            try:
                with Image.open(img_file) as img:
                    # Un hacker potrebbe inviare un file "SGI" o "PCX" corrotto
                    # che causa un crash o un overflow durante il caricamento dei pixel.
                    img.verify() 
                    img.thumbnail((100, 100))
                    img.save(f"thumb_{img_file.name}")
            except Exception as e:
                return render(request, 'error.html', {'error': str(e)})
                
    return render(request, 'upload.html', {'form': UploadForm()})

##VULNERABILITA' PYYAML
def safe_processor(data):
    # SCENARIO A: SAFE PATH (NOT VULNERABLE)
    # yaml.safe_load() only resolves standard YAML tags and is safe against RCE.
    print("Processing with safe_load...")
    return yaml.safe_load(data)

def unsafe_processor(data):
    # SCENARIO B: VULNERABLE PATH (REACHABLE RCE)
    # yaml.load() with FullLoader or without Loader is vulnerable in PyYAML < 5.4.
    # It allows instantiation of arbitrary Python objects.
    print("Processing with unsafe load (DANGER)...")
    return yaml.load(data, Loader=yaml.FullLoader)

if __name__ == "__main__":
    # Example YAML that could trigger RCE if loaded unsafely:
    # payload = "!!python/object/apply:os.system ['echo VULNERABLE > /tmp/hacked']"
    
    user_input = "name: Antigravity\nrole: Security Analyst"
    
    # By default, we use the safe path for normal operations
    result = safe_processor(user_input)
    print(f"Result: {result}")
    
    # To demonstrate a 'Reachable' vulnerability, uncomment the line below:
    unsafe_processor(user_input)
    print('Sto chiamando un metodo con vulnerabilita')
    request = ''
    upload_avatar(request)
    print('Sto chiamando un metodo con vulnerabilita per Pillow')
