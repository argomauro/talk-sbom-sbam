import yaml
import os

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
    #unsafe_processor(user_input)
