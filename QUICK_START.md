# Simple user manual

**Workflow: collect images → label → prepare dataset → train → evaluate → run robot.**

## 1. Install

Clone the repository, enter it, and install the Python packages:

```bash
git clone https://github.com/Leung555/coppeliasim-rotation-mapping.git
cd coppeliasim-rotation-mapping
python3 -m venv .venv
source .venv/bin/activate
python -m pip install -r requirements.txt
```

Activate `.venv` whenever you open a new terminal. The repository is private, so cloning requires GitHub access. Images, trained weights and the CoppeliaSim scene are not included.

## 2. Collect and label images

Collect clean images showing Cube and Tree from different angles and distances. Prefer the robot camera. In `main.py`, set your scene path and camera settings, set `"save_frames": True`, then run `python main.py`. Label the saved `output/rgb_*.png` images, not `frame_*.png` images with prediction overlays. Use a different `output_dir` for each collection to avoid overwriting files.

Install and launch Label Studio in its own environment:

```bash
python3 -m venv .venv-labelstudio
source .venv-labelstudio/bin/activate
python -m pip install -U label-studio
label-studio
```

In the browser:

1. Create a project and import your images.
2. Select the **Object Detection / Bounding Boxes** template.
3. Add **Cube** and **Tree** labels.
4. Draw a tight box around every target object and submit each image.
5. Export **YOLO with Images**, then extract the download.

Check the export's class mapping. The examples below use `0 = Cube`, `1 = Tree`. If your export differs, change the YAML names to match; do not just rename classes without checking IDs.

## 3. Prepare the dataset

Copy image/label pairs into this structure. An image and its `.txt` label must have the same filename stem:

```text
dataset/
├── images/
│   ├── train/cube01.png
│   └── val/tree01.png
└── labels/
    ├── train/cube01.txt
    └── val/tree01.txt
```

Both splits should contain examples of **both classes**. Keep a video or scene layout in one split; use separate recordings for validation. Reviewed images with no target objects can have empty label files.

Create the dataset configuration:

```bash
cp dataset.example.yaml dataset.yaml
```

Edit `dataset.yaml` with the actual absolute path of your dataset:

```yaml
path: /your/absolute/path/coppeliasim-rotation-mapping/dataset
train: images/train
val: images/val
names:
  0: Cube
  1: Tree
```

Changing YAML names does not change IDs in label files. Only IDs `0` and `1` are valid for this two-class example.

## 4. Train

Return to the project's environment:

```bash
source .venv/bin/activate
```

Without augmentation:

```bash
python train.py --epochs 100 --augmentation none --name objects_no_aug --device cpu
```

Or with mild augmentation:

```bash
python train.py --epochs 100 --augmentation mild --name objects_augmented --device cpu
```

For a compatible CUDA GPU, replace `--device cpu` with `--device 0`. The starting model is YOLO11 Nano. Its initial weights download requires internet access.

Training prints the output directory. Open `results.png` there for loss/accuracy curves. The trained model is `weights/best.pt` inside that directory. Repeated runs may append a number, such as `objects_no_aug2`; use that actual folder below.

## 5. Evaluate and view predictions

For the no-augmentation run:

```bash
python evaluate.py --weights runs/objects_no_aug/weights/best.pt --data dataset.yaml --preview
```

For the mild-augmentation run, replace `objects_no_aug` with `objects_augmented`.

Open the printed evaluation folder:

- `metrics.json`: precision, recall and mAP.
- `comparisons/*.png`: labels on the left, predictions on the right.
- `confusion_matrix.png`: correct classes, class confusion and unmatched detections.

In comparisons: **green = correct**, **red = false positive**, **orange = missed object**. The preview uses confidence 0.5 and requires the same class plus at least 0.5 box IoU. Review failures, improve the dataset, then retrain. Background in the confusion matrix is not an extra class to label.

## 6. Run the robot

Open CoppeliaSim and leave the simulation stopped. In `main.py`, edit `SETTINGS`:

- `scene_path`: your local `.ttt` scene file.
- Robot `/body`, left joint `/body/J1`, right joint `/body/J2`.
- Camera `/body/visionSensor`.
- Actual wheel radius, wheel spacing and joint signs.

Enable the ZMQ remote API and velocity-controlled wheel motors. Use a perspective camera with RGB and depth enabled. Disable other motor controllers and the image-modification script from `cv_example`. The scene must use the expected body axes described in the README.

First check a small rotation with `python main.py --odom-only`. Then run with your custom model:

```bash
python main.py --weights runs/objects_no_aug/weights/best.pt
```

Python loads the configured scene, starts the simulation, rotates the robot, prints detections and saves:

```text
output/map.png          # Object locations
output/objects.json     # Classes and coordinates
output/odometry.csv     # Robot position and heading
```

A completed rotation does not guarantee successful detections. If zero objects are saved, check the printed weights/classes, confidence, camera input and depth messages.

For more detail, see [README.md](README.md) and [TRAINING_GUIDE.md](TRAINING_GUIDE.md).
