from flask import Flask, render_template, request, jsonify, send_file, session
import websocket
import uuid
import json
import urllib.request
import urllib.parse
import io
import random
from threading import Thread, Lock
import time
import os
import subprocess
import signal
from datetime import datetime
from collections import deque
from functools import wraps

app = Flask(__name__)
app.secret_key = os.urandom(24)

# Configuration
CONFIG_FILE = 'brasswick_config.json'
DEFAULT_CONFIG = {
    'comfy_server': '127.0.0.1:8188',
    'comfy_path': '/path/to/ComfyUI',
    'multi_user': False,
    'max_history': 50,
    'port': 5000
}

def load_config():
    if os.path.exists(CONFIG_FILE):
        with open(CONFIG_FILE, 'r') as f:
            return {**DEFAULT_CONFIG, **json.load(f)}
    return DEFAULT_CONFIG

def save_config(config):
    with open(CONFIG_FILE, 'w') as f:
        json.dump(config, f, indent=2)

config = load_config()
COMFY_SERVER = config['comfy_server']
MULTI_USER = config['multi_user']
MAX_HISTORY = config['max_history']

# ComfyUI process management
comfy_process = None

# Client ID management
def get_client_id():
    if MULTI_USER:
        if 'client_id' not in session:
            session['client_id'] = str(uuid.uuid4())
        return session['client_id']
    return 'default_client'

# Thread safety
state_lock = Lock()

# Per-user state storage
user_states = {}

def get_user_state():
    client_id = get_client_id()
    if client_id not in user_states:
        user_states[client_id] = {
            'queue': deque(),
            'is_generating': False,
            'generation_state': {
                'status': 'idle',
                'progress': 0,
                'has_image': False,
                'error': None,
                'current_prompt_id': None,
                'eta_seconds': 0,
                'queue_position': 0,
                'queue_total': 0
            },
            'current_image_data': None,
            'history': []
        }
    return user_states[client_id]

def queue_prompt(prompt, prompt_id):
    """Queue a prompt to ComfyUI"""
    p = {"prompt": prompt, "client_id": get_client_id(), "prompt_id": prompt_id}
    data = json.dumps(p).encode('utf-8')
    req = urllib.request.Request(f"http://{COMFY_SERVER}/prompt", data=data)
    return urllib.request.urlopen(req).read()

def get_image(filename, subfolder, folder_type):
    """Retrieve generated image from ComfyUI"""
    data = {"filename": filename, "subfolder": subfolder, "type": folder_type}
    url_values = urllib.parse.urlencode(data)
    with urllib.request.urlopen(f"http://{COMFY_SERVER}/view?{url_values}") as response:
        return response.read()

def get_history_data(prompt_id):
    """Get generation history"""
    with urllib.request.urlopen(f"http://{COMFY_SERVER}/history/{prompt_id}") as response:
        return json.loads(response.read())

def get_queue_info():
    """Get current queue information from ComfyUI"""
    try:
        with urllib.request.urlopen(f"http://{COMFY_SERVER}/queue") as response:
            data = json.loads(response.read())
            return data
    except:
        return {'queue_running': [], 'queue_pending': []}

def interrupt_generation():
    """Interrupt current generation"""
    try:
        req = urllib.request.Request(f"http://{COMFY_SERVER}/interrupt", method='POST')
        urllib.request.urlopen(req)
        return True
    except:
        return False

def get_models():
    """Fetch available models from ComfyUI"""
    try:
        with urllib.request.urlopen(f"http://{COMFY_SERVER}/object_info/CheckpointLoaderSimple") as response:
            data = json.loads(response.read())
            return data['CheckpointLoaderSimple']['input']['required']['ckpt_name'][0]
    except Exception as e:
        print(f"Error loading models: {e}")
        return []

def get_loras():
    """Fetch available LoRAs from ComfyUI"""
    try:
        with urllib.request.urlopen(f"http://{COMFY_SERVER}/object_info") as response:
            data = json.loads(response.read())
            
            if 'CR LoRA Stack' in data:
                lora_list = data['CR LoRA Stack']['input']['required']['lora_name_1'][0]
                return lora_list
            
            if 'LoraLoader' in data:
                lora_list = data['LoraLoader']['input']['required']['lora_name'][0]
                return lora_list
                
        return ["None"]
    except Exception as e:
        print(f"Error loading LoRAs: {e}")
        return ["None"]

def get_samplers():
    """Fetch available samplers from ComfyUI"""
    try:
        with urllib.request.urlopen(f"http://{COMFY_SERVER}/object_info/KSampler") as response:
            data = json.loads(response.read())
            return data['KSampler']['input']['required']['sampler_name'][0]
    except:
        return ['euler', 'euler_ancestral', 'heun', 'dpm_2', 'dpm_2_ancestral', 
                'lms', 'dpm_fast', 'dpm_adaptive', 'dpmpp_2s_ancestral', 
                'dpmpp_sde', 'dpmpp_2m', 'ddim', 'uni_pc']

def get_schedulers():
    """Fetch available schedulers from ComfyUI"""
    try:
        with urllib.request.urlopen(f"http://{COMFY_SERVER}/object_info/KSampler") as response:
            data = json.loads(response.read())
            return data['KSampler']['input']['required']['scheduler'][0]
    except:
        return ['normal', 'karras', 'exponential', 'simple', 'ddim_uniform']

def build_workflow(params):
    """Build ComfyUI workflow from parameters"""
    workflow = {
        "1": {
            "inputs": {
                "ckpt_name": params['model']
            },
            "class_type": "CheckpointLoaderSimple",
            "_meta": {"title": "Load Checkpoint"}
        },
        "4": {
            "inputs": {
                "switch_1": "On" if params.get('lora_1_name') and params['lora_1_name'] != "None" else "Off",
                "lora_name_1": params.get('lora_1_name', 'None'),
                "model_weight_1": params.get('lora_1_weight', 1),
                "clip_weight_1": params.get('lora_1_weight', 1),
                "switch_2": "On" if params.get('lora_2_name') and params['lora_2_name'] != "None" else "Off",
                "lora_name_2": params.get('lora_2_name', 'None'),
                "model_weight_2": params.get('lora_2_weight', 1),
                "clip_weight_2": params.get('lora_2_weight', 1),
                "switch_3": "On" if params.get('lora_3_name') and params['lora_3_name'] != "None" else "Off",
                "lora_name_3": params.get('lora_3_name', 'None'),
                "model_weight_3": params.get('lora_3_weight', 1),
                "clip_weight_3": params.get('lora_3_weight', 1)
            },
            "class_type": "CR LoRA Stack",
            "_meta": {"title": "💊 CR LoRA Stack"}
        },
        "12": {
            "inputs": {
                "images": ["8:8", 0]
            },
            "class_type": "PreviewImage",
            "_meta": {"title": "Preview Image"}
        },
        "16": {
            "inputs": {
                "width": params['width'],
                "height": params['height'],
                "batch_size": params['batch_size']
            },
            "class_type": "EmptyLatentImage",
            "_meta": {"title": "Empty Latent Image"}
        },
        "8:8": {
            "inputs": {
                "samples": ["8:7", 0],
                "vae": ["1", 2]
            },
            "class_type": "VAEDecode",
            "_meta": {"title": "VAE Decode"}
        },
        "8:5": {
            "inputs": {
                "text": params['positive_prompt'],
                "clip": ["8:3", 1]
            },
            "class_type": "CLIPTextEncode",
            "_meta": {"title": "CLIP Text Encode (Prompt)"}
        },
        "8:6": {
            "inputs": {
                "text": params['negative_prompt'],
                "clip": ["8:3", 1]
            },
            "class_type": "CLIPTextEncode",
            "_meta": {"title": "CLIP Text Encode (Prompt)"}
        },
        "8:3": {
            "inputs": {
                "model": ["1", 0],
                "clip": ["1", 1],
                "lora_stack": ["4", 0]
            },
            "class_type": "CR Apply LoRA Stack",
            "_meta": {"title": "💊 CR Apply LoRA Stack"}
        },
        "8:7": {
            "inputs": {
                "seed": params['seed'],
                "steps": params['steps'],
                "cfg": params['cfg'],
                "sampler_name": params.get('sampler', 'euler_ancestral'),
                "scheduler": params.get('scheduler', 'normal'),
                "denoise": 1,
                "model": ["8:3", 0],
                "positive": ["8:5", 0],
                "negative": ["8:6", 0],
                "latent_image": ["16", 0]
            },
            "class_type": "KSampler",
            "_meta": {"title": "KSampler"}
        }
    }
    return workflow

def add_to_history(image_data, params, prompt_id):
    """Add generated image to history"""
    state = get_user_state()
    
    history_entry = {
        'id': prompt_id,
        'timestamp': datetime.now().isoformat(),
        'params': params.copy(),
        'image_data': image_data
    }
    
    state['history'].insert(0, history_entry)
    
    if len(state['history']) > MAX_HISTORY:
        state['history'] = state['history'][:MAX_HISTORY]

def generate_image(params):
    """Generate image using ComfyUI"""
    state = get_user_state()
    
    try:
        with state_lock:
            state['generation_state']['status'] = 'generating'
            state['generation_state']['progress'] = 0
            state['generation_state']['error'] = None
            state['generation_state']['has_image'] = False
            state['generation_state']['eta_seconds'] = 0
        
        state['current_image_data'] = None
        
        workflow = build_workflow(params)
        prompt_id = str(uuid.uuid4())
        
        with state_lock:
            state['generation_state']['current_prompt_id'] = prompt_id
        
        ws = websocket.WebSocket()
        ws.connect(f"ws://{COMFY_SERVER}/ws?clientId={get_client_id()}")
        
        queue_prompt(workflow, prompt_id)
        
        start_time = time.time()
        
        while True:
            out = ws.recv()
            if isinstance(out, str):
                message = json.loads(out)
                
                if message['type'] == 'executing':
                    data = message['data']
                    if data['node'] is None and data['prompt_id'] == prompt_id:
                        break
                        
                elif message['type'] == 'progress':
                    current = message['data']['value']
                    total = message['data']['max']
                    progress = int((current / total) * 100)
                    
                    elapsed = time.time() - start_time
                    if current > 0:
                        eta = (elapsed / current) * (total - current)
                    else:
                        eta = 0
                    
                    with state_lock:
                        state['generation_state']['progress'] = progress
                        state['generation_state']['eta_seconds'] = int(eta)
            else:
                # Binary preview data - save for live preview
                if len(out) > 8:
                    state['current_image_data'] = out[8:]
        
        ws.close()
        
        history = get_history_data(prompt_id)[prompt_id]
        for node_id in history['outputs']:
            node_output = history['outputs'][node_id]
            if 'images' in node_output:
                for image in node_output['images']:
                    image_data = get_image(image['filename'], image['subfolder'], image['type'])
                    state['current_image_data'] = image_data
                    
                    add_to_history(image_data, params, prompt_id)
                    
                    with state_lock:
                        state['generation_state']['has_image'] = True
                        state['generation_state']['status'] = 'complete'
                    return
        
        with state_lock:
            state['generation_state']['status'] = 'complete'
        
    except Exception as e:
        with state_lock:
            state['generation_state']['status'] = 'error'
            state['generation_state']['error'] = str(e)
        print(f"Generation error: {e}")
    finally:
        state['is_generating'] = False
        process_queue()

def process_queue():
    """Process next item in queue"""
    state = get_user_state()
    
    with state_lock:
        if state['is_generating'] or len(state['queue']) == 0:
            return
        
        state['is_generating'] = True
        params = state['queue'].popleft()
        state['generation_state']['queue_total'] = len(state['queue'])
    
    thread = Thread(target=generate_image, args=(params,))
    thread.daemon = True
    thread.start()

# Server management functions
def start_comfy_server():
    """Start ComfyUI server"""
    global comfy_process
    if comfy_process is None:
        try:
            comfy_path = config['comfy_path']
            comfy_process = subprocess.Popen(
                ['python', 'main.py'],
                cwd=comfy_path,
                stdout=subprocess.PIPE,
                stderr=subprocess.PIPE
            )
            return True
        except Exception as e:
            print(f"Failed to start ComfyUI: {e}")
            return False
    return False

def stop_comfy_server():
    """Stop ComfyUI server"""
    global comfy_process
    if comfy_process:
        comfy_process.terminate()
        comfy_process.wait()
        comfy_process = None
        return True
    return False

def restart_comfy_server():
    """Restart ComfyUI server"""
    stop_comfy_server()
    time.sleep(2)
    return start_comfy_server()

# Routes
@app.route('/')
def index():
    return render_template('index.html')

@app.route('/api/models')
def api_models():
    return jsonify(get_models())

@app.route('/api/loras')
def api_loras():
    return jsonify(get_loras())

@app.route('/api/samplers')
def api_samplers():
    return jsonify(get_samplers())

@app.route('/api/schedulers')
def api_schedulers():
    return jsonify(get_schedulers())

@app.route('/api/generate', methods=['POST'])
def api_generate():
    params = request.json
    state = get_user_state()
    
    if params.get('seed') == -1:
        params['seed'] = random.randint(0, 2**32 - 1)
    
    with state_lock:
        state['queue'].append(params)
        queue_pos = len(state['queue'])
    
    process_queue()
    
    return jsonify({'status': 'queued', 'seed': params['seed'], 'position': queue_pos})

@app.route('/api/cancel', methods=['POST'])
def api_cancel():
    state = get_user_state()
    success = interrupt_generation()
    
    with state_lock:
        state['generation_state']['status'] = 'cancelled'
        state['generation_state']['error'] = 'Generation cancelled by user'
    
    return jsonify({'success': success})

@app.route('/api/clear_queue', methods=['POST'])
def api_clear_queue():
    state = get_user_state()
    with state_lock:
        state['queue'].clear()
        state['generation_state']['queue_total'] = 0
    
    return jsonify({'success': True})

@app.route('/api/status')
def api_status():
    state = get_user_state()
    with state_lock:
        queue_info = get_queue_info()
        
        return jsonify({
            'status': state['generation_state']['status'],
            'progress': state['generation_state']['progress'],
            'has_image': state['generation_state']['has_image'],
            'error': state['generation_state']['error'],
            'eta_seconds': state['generation_state']['eta_seconds'],
            'queue_pending': len(state['queue']),
            'queue_running': len(queue_info.get('queue_running', []))
        })

@app.route('/api/image')
def api_image():
    state = get_user_state()
    if state['current_image_data']:
        return send_file(
            io.BytesIO(state['current_image_data']),
            mimetype='image/png',
            as_attachment=False,
            download_name='generated.png'
        )
    return '', 404

@app.route('/api/image/download')
def api_image_download():
    state = get_user_state()
    if state['current_image_data']:
        return send_file(
            io.BytesIO(state['current_image_data']),
            mimetype='image/png',
            as_attachment=True,
            download_name=f'brasswick_{int(time.time())}.png'
        )
    return '', 404

@app.route('/api/history')
def api_history():
    state = get_user_state()
    history_meta = []
    for entry in state['history']:
        history_meta.append({
            'id': entry['id'],
            'timestamp': entry['timestamp'],
            'params': entry['params']
        })
    return jsonify(history_meta)

@app.route('/api/history/<history_id>')
def api_history_image(history_id):
    state = get_user_state()
    for entry in state['history']:
        if entry['id'] == history_id:
            return send_file(
                io.BytesIO(entry['image_data']),
                mimetype='image/png'
            )
    return '', 404

@app.route('/api/history/<history_id>/download')
def api_history_download(history_id):
    state = get_user_state()
    for entry in state['history']:
        if entry['id'] == history_id:
            return send_file(
                io.BytesIO(entry['image_data']),
                mimetype='image/png',
                as_attachment=True,
                download_name=f'brasswick_{history_id}.png'
            )
    return '', 404

@app.route('/api/server/start', methods=['POST'])
def api_server_start():
    success = start_comfy_server()
    return jsonify({'success': success})

@app.route('/api/server/stop', methods=['POST'])
def api_server_stop():
    success = stop_comfy_server()
    return jsonify({'success': success})

@app.route('/api/server/restart', methods=['POST'])
def api_server_restart():
    success = restart_comfy_server()
    return jsonify({'success': success})

@app.route('/api/config', methods=['GET', 'POST'])
def api_config():
    global config, COMFY_SERVER, MULTI_USER, MAX_HISTORY
    
    if request.method == 'POST':
        new_config = request.json
        config = {**config, **new_config}
        save_config(config)
        
        COMFY_SERVER = config['comfy_server']
        MULTI_USER = config['multi_user']
        MAX_HISTORY = config['max_history']
        
        return jsonify({'success': True})
    
    return jsonify(config)

if __name__ == '__main__':
    os.makedirs('templates', exist_ok=True)
    app.run(debug=True, host='0.0.0.0', port=config['port'], threaded=True)