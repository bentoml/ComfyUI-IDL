# Comfy-Pack: Making ComfyUI Workflows Portable

![image](https://github.com/user-attachments/assets/f2e55cd5-9efe-4887-896e-5b80b37318c5)

A comprehensive toolkit for reliably packing and unpacking environments for ComfyUI workflows. 


- 📦 **Pack workflow environments as artifacts:** Saves the workflow environment in a `.cpack.zip` artifact with Python package versions, ComfyUI and custom node revisions, and model hashes.
- ✨ **Unpack artifacts to recreate workflow environments:** Unpacks the `.cpack.zip` artifact to recreate the same environment with the exact Python package versions, ComfyUI and custom node revisions, and model weights.
- 🚀 **Deploy workflows as APIs:** Deploys the workflow as a RESTful API with customizable input and output parameters.

## Motivations

When sharing ComfyUI workflows to others, your audiences or team member, you've likely heard these responses:
- "Custom Node not found"
- "Cannot find the model file"
- "Missing Python dependencies"

These are fundamental challenges in workflow sharing – every component must match exactly: custom nodes, model files, and Python dependencies.

We learned it from our communit, and developed Comfy-Pack to address this directly. With a single click, it captures and locks your entire workflow environment into a `.cpack.zip` file, including Python packages, custom nodes, model hashes, and required assets.

Users can recreate the exact environment with one command:
```bash
comfy-pack unpack workflow.cpack.zip
```

Focus on creating. Let Comfy-Pack handle the rest.

## Usages

### Installation

Search `comfy-pack` in ComfyUI Manager (Recommended)

![install_node](https://github.com/user-attachments/assets/dbfb730d-edff-4a52-b6c4-695e3ec70368)

or install from Git:

```bash
git clone https://github.com/bentoml/comfy-pack.git
```

### 📦 Pack a ComfyUI workflow and its environment

Packing a workflow and the environment required to run the workflow into an artifact that can be unpacked elsewhere.

1. Click "Package" button to create a `.cpack.zip` artifact.
2. (Optional) select the models that you want to include (only model hash will be recorded, so you wont get a 100GB zip file).

![pack](https://github.com/user-attachments/assets/e08bbed2-84dc-474e-a701-6c6db16edf76)


### ✨ Unpack the ComfyUI environments

Unpacking a `.cpack.zip` artifact will restore the ComfyUI environment for the workflow. During unpacking, comfy-pack will perform the following steps.

1. Prepare a Python virtual environment with the exact packages used to run the workflow.
2. Clone ComfyUI and custom nodes from the exact revisions required by the workflow.
3. Search and download models from common registries like Hugging Face and Civitai. Unpacking workflows using the same model will not cause the model to be downloaded multiple times. Instead model weights will symbolically linked.

```bash
comfy-pack unpack workflow.cpack.zip
```
For example cpack files, check our [examples folder](examples/).

### 🏗️ Install the newest ComfyUI & init a project from sketch

```bash
comfy-pack init
```

### 🚀 Deploy a workflow as an API

Deployment turns the ComfyUI workflow into an API endpoint callable using any clients through HTTP.


<details>
<summary> 1. Annotate input & output </summary>

Use custom nodes provided by comfy-pack to annotate the fields to be used as input and output parameters.

- ImageInput: provides `image` type input, similar to official `LoadImage` node
- StringInput: provides `string` type input, nice for prompts
- IntInput: provides `int` type input, suitable for size or seeds
- AnyInput: provides `combo` type and more input, suitable for custom nodes
- ImageOutput: takes `image` type inputs, similar to official `SaveImage` node, take an image of a bunch of images
- FileOutput: takes file path as `string` type, save and output the file under that path
- More underway.
  
![input](https://github.com/user-attachments/assets/44264007-0ac8-4e23-8dc0-e60aa0ebcea2)

![output](https://github.com/user-attachments/assets/a4526661-8930-4575-bacc-33b6887f6271)
</details>

<details>
<summary> 2. Serve the workflow </summary>

Start an HTTP server to serve the workflow under `/generate` path.

![serve](https://github.com/user-attachments/assets/8d4c92c5-d6d7-485e-bc71-e4fc0fe8bf35)
</details>

<details>
<summary> 3. (Optional) Pack the workflow and environment </summary>

Pack the workflow and environment into an artifact that can be unpacked elsewhere to recreate the workflow.

```bash
# Get the workflow input spec
comfy-pack run workflow.cpack.zip --help

# Run
comfy-pack run workflow.cpack.zip --src-image image.png --video video.mp4
```
</details>

<details> 
<summary> 4. (Optional) Deploy to the cloud </summary>

Deploy to BentoCloud with access to a variety of GPUs and blazing fast scaling.

![image](https://github.com/user-attachments/assets/1ffa31fc-1f50-4ea7-a47e-7dae3b874273)

</details>

## 🚀 Roadmap
This project is under active development.
- Better UX
- Docker support
- Local cpack manager and version control
- Enhanced service capabilities


## License
Apache 2.0

## Community
- Issues & Feature Requests: GitHub Issues
- Questions & Discussion: Discord Server

Detailed documentation: under development
