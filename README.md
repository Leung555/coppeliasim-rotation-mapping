# Rotation odometry and object mapping

**Start here: [Simple user manual](QUICK_START.md)** — install, label images, train, evaluate, and run the robot.

External Python controller for your existing CoppeliaSim scene. It rotates a differential-drive robot, integrates measured wheel angles, detects objects using YOLO, and projects detections into a simple 2D landmark map using camera depth. It does not require an embedded Python interpreter in CoppeliaSim.

## Training and evaluation commands

Choose your augmentation profile explicitly:

| Option | Behavior |
|---|---|
| `--augmentation none` | Disable training transformations; retain resizing and normalization |
| `--augmentation mild` | Project's mild transformations (default when omitted) |
| `--augmentation default` | Ultralytics built-in augmentation defaults |

For training without augmentation, use the [no-augmentation workflow](#train-without-augmentation) below.

Run these commands from `SIIT/rotation_mapping` after activating your Python environment with the project dependencies. CoppeliaSim is not needed for training/evaluation.

```bash
# 1. Train Nano with mild augmentation.
python train.py --data dataset.yaml --model yolo11n.pt --epochs 100 --imgsz 640 --augmentation mild --name objects_augmented --device cpu

# 2. Evaluate and save ground-truth/prediction comparisons.
python evaluate.py --weights runs/objects_augmented/weights/best.pt --data dataset.yaml --split val --imgsz 640 --device cpu --preview --preview-conf 0.5 --match-iou 0.5

# 3. Run the robot with these weights (CoppeliaSim must be open and stopped).
python main.py --weights runs/objects_augmented/weights/best.pt
```

If training prints an incremented folder such as `objects_augmented2`, use that folder in both following commands. GPU users can replace `--device cpu` with `--device 0` for training and evaluation.

Open the training run's `results.png` for loss and metric curves, or `results.csv` for per-epoch values. Evaluation prints its actual `runs/evaluation*` folder; open `comparisons/*.png`, `metrics.json`, and the confusion-matrix plots there. Green preview predictions are correct, red are false positives, and orange ground-truth boxes are missed. Official metric values may differ from preview counts because their thresholds differ.

For a comparison against the original augmentation defaults:

```bash
python train.py --data dataset.yaml --model yolo11n.pt --epochs 100 --imgsz 640 --augmentation default --name objects_baseline --device cpu
python evaluate.py --weights runs/objects_baseline/weights/best.pt --data dataset.yaml --imgsz 640 --device cpu --preview
```

Keep the dataset split fixed when comparing runs. `--split test` requires an existing labeled test set and a `test` entry in the YAML; it is not ready in the current dataset. A five-epoch pilot should use a separate `--name objects_pilot` so it stays distinct from full training.

## Project structure

```text
rotation_mapping/
├── main.py                 # Settings, all runtime functions and robot loop
├── train.py                # Custom YOLO training
├── evaluate.py             # Validation/test detection metrics
├── test_main.py            # Automated odometry and projection tests
├── dataset.example.yaml    # Dataset configuration template
├── requirements.txt        # Python dependencies
├── QUICK_START.md           # Simple step-by-step user manual
├── TRAINING_GUIDE.md        # Custom dataset training instructions
├── README.md
├── dataset/                # Your images and labels (not included)
├── captures/               # Optional images collected for labeling
├── runs/                   # Generated training/evaluation artifacts
└── output/                 # Generated odometry, objects and map
```

All robot runtime code stays in `main.py`. Training and evaluation are separate; the runtime loads YOLO weights through `--weights` or `SETTINGS["model"]`.

## Tech stack

| Component | Technology | Role |
|---|---|---|
| Simulator | CoppeliaSim Edu 4.10 scene | Simulated robot, motors, RGB and depth sensor |
| Application | Python | Main loop, training and evaluation scripts |
| Robot connection | `coppeliasim-zmqremoteapi-client` / ZeroMQ | Remote commands and synchronized simulation steps |
| Detector | Ultralytics YOLO11 Nano (`yolo11n.pt`) | Baseline detector and starting weights for custom training |
| Annotation tool | Label Studio (optional, installed separately) | Draw bounding boxes and export YOLO labels |
| Training engine | PyTorch, used by Ultralytics | CPU or compatible GPU model training/inference |
| Image processing | OpenCV | RGB/BGR conversion and optional CLAHE |
| Numerical processing | NumPy | Image/depth buffers and median depth selection |
| Localization | Differential-drive encoder odometry + camera depth | Robot pose and approximate object surface locations |
| Visualization | Matplotlib | Static labeled 2D map |
| Saved data | CSV and JSON | Odometry trajectory and landmark records |
| Automated checks | Python `unittest` | Geometry and association tests |

The configured detector is [YOLO11 Nano](https://docs.ultralytics.com/models/yolo11). The pretrained model recognizes COCO classes; custom scene object classes require your labeled dataset. Dependencies are listed in `requirements.txt`.

## Runtime flow

`Load YOLO weights → connect via ZMQ → load scene → find robot/camera → start simulation → repeat: update encoder odometry, detect and map objects, command wheel speeds, advance simulation → stop and save outputs`.

The configured scene is `/home/binggwong/CoppeliaSim_Edu_V4_10_0_rev0_Ubuntu24_04/scenes/SIIT Class/Demo_CV.ttt`. Paths and robot dimensions are editable at the top of `main.py`.

## Scene setup

1. Open CoppeliaSim and leave the simulation stopped. Enable the ZMQ remote API add-on (normally enabled by default). The controller loads `Demo_CV.ttt` from `SETTINGS["scene_path"]` before finding the robot and camera. Save any current scene edits before running. Set `scene_path` to an empty string to use the currently open scene instead.
2. Robot and joints use `/body`, `/body/J1` (left), `/body/J2` (right).
3. Configure both joints for velocity control with enough motor torque. Disable other scripts that write motor velocities.
4. Attach a perspective vision sensor rigidly to the body. The camera path is `/body/visionSensor`, configured in `SETTINGS` at the top of `main.py`. Enable RGB and depth, disable external input, and use a normal RGB render mode. Non-explicit sensors are handled by the normal main script; explicit sensors are handled by this controller.
5. Disable the image modification callback from `../CV/cv_example` on this sensor, including its periodic `sysCall_sensing` handler. That callback adds edges, tint, a circle, channel conversion, and flipping, which corrupt the detector's input and RGB/depth alignment. Keep the original example for reference. Python performs the vertical flip, RGB-to-BGR conversion and optional CLAHE itself.
6. Measure wheel radius and distance between wheel centres in metres. The example values `0.05` and `0.30` are placeholders. Body local axes must be +X forward, +Y left, +Z up; the odometry origin is the initial body frame. Camera pose relative to body is read once from the scene.
7. Set `left_sign` and `right_sign` so positive signed encoder motion means forward wheel motion. A reversed joint axis needs `-1`. Ensure each wheel moves less than pi radians per simulation step to avoid encoder wrap ambiguity.

## Install and run

From this directory:

```bash
python3 -m venv .venv
source .venv/bin/activate
python -m pip install -r requirements.txt
python main.py --odom-only
python main.py
```

First check a small rotation (for example `rotation_deg: 30`) with `--odom-only`. Positive rotation should turn counterclockwise when viewed from above. Calibrate wheel dimensions and joint signs before doing a full scan. Encoder odometry measures wheel motion, so slip affects accuracy; compare the physical rotation in the simulator with the reported angle.

`rotation_deg` defaults to 360; negative values rotate clockwise. Control slows near the target and stops within the configured tolerance. A simulation-time timeout catches stalled or misconfigured motors. The controller stops motors and simulation and saves partial results on normal Python exceptions or Ctrl+C. Close the simulation manually if the remote connection is lost.

`yolo11n.pt` is a pretrained baseline and is downloaded on first use. It recognizes its built-in COCO classes; it is not trained to recognize arbitrary simulated cubes, cylinders, or spheres. Use a custom dataset for those objects. `"save_frames": True` saves clean `rgb_*.png` images for labeling and annotated `frame_*.png` images for review; set `confidence`, optional `clahe`, and `detect_every_steps` as needed. Match preprocessing between training and inference.

## Label images with Label Studio

If it is already installed, activate its virtual environment and run `label-studio`. To install it in an activated environment:

```bash
python -m pip install -U label-studio
label-studio
```

Create a bounding-box project, import clean `rgb_*.png` captures, label all target objects, and export in YOLO format. Check the exported class IDs against your dataset YAML before training. See the [Label Studio workflow in the training guide](TRAINING_GUIDE.md#4-annotate-bounding-boxes) for setup, labeling configuration and export steps, based on the official [Label Studio quick start](https://labelstud.io/guide/quick_start.html).

## Train your object types

Follow [TRAINING_GUIDE.md](TRAINING_GUIDE.md) for collecting clean sensor images, annotating YOLO bounding boxes, splitting scenes, configuring classes, training, evaluating and using your weights. It includes a worked label example and troubleshooting.

After preparing your labeled dataset and `dataset.yaml`:

```bash
python train.py --data dataset.yaml --model yolo11n.pt --epochs 100 --imgsz 640 --augmentation mild --name objects_augmented --device cpu
```

Use `--device 0` for a compatible GPU. The script prints the actual training directory; repeated runs may increment its name. No custom dataset or trained weights are bundled.

## Improve model accuracy

See [Improve the Bowl, Cube and Tree detector](TRAINING_GUIDE.md#improve-the-bowl-cube-and-tree-detector). The corrected dataset has 24 training images and 17 validation screenshots, with Cube and Tree classes. The earlier 12-image dataset was a workflow check. Prioritize varied sensor captures, consistent labels and scene-separated validation before increasing training time. The guide includes baseline commands, model/image-size comparisons, failure analysis and the distinction between detection and map errors.

## Evaluate trained weights

```bash
python evaluate.py --weights runs/objects_augmented/weights/best.pt --data dataset.yaml
python main.py --weights runs/objects_augmented/weights/best.pt
```

Evaluation saves precision, recall, mAP metrics, and plots under `runs/evaluation` (the run directory may increment). For a held-out test set, add `test: images/test` to your dataset YAML and pass `--split test`. This evaluates detection quality; map accuracy still needs checking in your scene.

## Outputs and interpretation

- `output/odometry.csv`: simulation time, x/y in metres, unwrapped heading in radians.
- `output/objects.json`: estimated x/y by object type and instance, observation count, maximum confidence.
- `output/map.png`: robot trajectory and labeled object locations.
- `output/rgb_*.png`: optional clean RGB images for labeling.
- `output/frame_*.png`: optional annotated detections.

Wheel odometry uses `dl = radius * delta_left`, `dr = radius * delta_right`, `dtheta = (dr-dl)/track` and exact arc integration. A full revolution is tracked without wrapping heading back to zero. Robot world pose and object ground-truth positions are not used.

Localization uses median metric axial depth in a small patch at each bounding-box centre, camera intrinsics derived from resolution and perspective angle, the camera-to-body transform, and the encoder pose. Background/far-plane readings are rejected. Locations estimate a visible surface point, not the object's geometric centre. A centre patch can hit background or an occluder; segmentation or robust foreground depth selection is a future improvement. Objects of the same class closer than `merge_radius_m` may merge; drift can also split one object into several landmarks. This is an approximate landmark map, not an occupancy grid or SLAM system. Pure rotation without depth cannot determine unknown object distances.

## Verification

```bash
python -m unittest discover -s . -p 'test_*.py' -v
```

Tests cover straight travel, curved motion, encoder wrapping, a full rotation, camera projection and nearby landmark association. End-to-end operation requires your scene, dependencies and detector weights.

API references: [CoppeliaSim metric depth](https://manual.coppeliarobotics.com/en/sim/simGetVisionSensorDepth.htm), [vision sensor settings](https://manual.coppeliarobotics.com/en/visionSensorPropertiesDialog.htm), [Ultralytics Python training and prediction](https://docs.ultralytics.com/usage/python).

## Current imported dataset

The active class mapping is `0: Cube`, `1: Tree`. Training uses 24 cropped video images (9 Cube, 15 Tree). Validation uses 17 separate screenshots with 6 Cube boxes, 5 Tree boxes and 7 empty annotations. Review empty labels to confirm no target was omitted. No test split is configured.

The original flat export stays in `dataset/images/` and `dataset/labels/`. The YAML reads the `train` and `val` subfolders, so new exported files must be placed in the appropriate split before training. See `dataset/README.md` and `dataset/split_report.json`.


## View labels beside predictions

```bash
python evaluate.py --weights runs/objects_augmented/weights/best.pt --data dataset.yaml --preview
```

Open the PNG images in the printed `runs/evaluation*/comparisons/` folder. Each image shows ground-truth boxes on the left and predictions on the right. Green predictions are correct matches, red predictions are unmatched/incorrect, and orange ground-truth boxes are missed. A correct match needs the same class and at least 0.5 intersection-over-union (IoU), with one prediction per label.

The preview defaults to confidence 0.5, matching the robot setting. Use `--preview-conf 0.25` to inspect weaker predictions or `--match-iou 0.75` for stricter overlap. These are diagnostic counts, not a replacement for Ultralytics mAP: official metrics use multiple thresholds and may differ. Wrong-class boxes count as both a false positive and a missed ground-truth object. Missing label files are treated as empty and reported with a warning, so check that labels are complete before judging correctness. `summary.json` records counts per image.

Standard evaluation also saves confusion matrices and batch label/prediction plots with `plots=True`, as described in the official [validation documentation](https://docs.ultralytics.com/modes/val).

## Mild augmentation experiment

`train.py` now defaults to a mild augmentation profile. Images and bounding boxes are transformed together during training; original files and validation images are unchanged. This is a candidate recipe, not a proven improvement. The earlier baseline already used Ultralytics default augmentations.

| Setting | Mild profile | Purpose |
|---|---|---|
| HSV hue/saturation/value | 0.01 / 0.25 / 0.25 | Modest color and brightness variation |
| Rotation | ±5 degrees | Small camera tilt |
| Translation | 0.1 | Position shifts up to a fraction of image dimensions |
| Scale | 0.25 | Random scale gain roughly 0.75–1.25 |
| Horizontal flip | 50% probability | Left/right variation |
| Vertical flip, shear, perspective | Disabled | Keep upright scenes plausible |
| Mosaic | 30% probability | Combine scenes to vary composition |
| MixUp and copy-paste | Disabled | Keep the starting experiment simple |

Mosaic is disabled for the last `min(10, epochs // 5)` epochs. Other transformations stay active. Optional library transforms may still depend on installed packages; inspect the training log and saved `args.yaml`. See the official [augmentation guide](https://docs.ultralytics.com/guides/yolo-data-augmentation).

Run the experiment from the project directory:

```bash
python train.py --epochs 100 --augmentation mild --name objects_augmented --device cpu
python evaluate.py --weights runs/objects_augmented/weights/best.pt --data dataset.yaml --preview
```

Repeated names may be incremented; use the output path printed by training. To compare against the original library defaults on the same fixed dataset:

```bash
python train.py --epochs 100 --augmentation default --name objects_baseline --device cpu
```

Compare both runs on the same validation split, image size and preview confidence. Review per-class misses, false positives and training batch plots (`train_batch*.jpg`). Keep the profile only if held-out performance improves. More augmentation cannot replace new camera views or independent recordings. No new training run is started automatically by this change.

## Train without augmentation

```bash
python train.py --data dataset.yaml --model yolo11n.pt --epochs 100 --imgsz 640 --augmentation none --name objects_no_aug --device cpu
python evaluate.py --weights runs/objects_no_aug/weights/best.pt --data dataset.yaml --split val --imgsz 640 --device cpu --preview --preview-conf 0.5
```

`none` zeros color and geometric transformations, flipping, mosaic, MixUp and copy-paste, and disables the optional Albumentations wrapper in the training process. Required resizing/letterboxing and normalization remain. `default` still enables Ultralytics default augmentation; it does not mean augmentation is off. Use the actual run folder printed by training if its name increments.

For this run, inspect `runs/objects_no_aug/results.png` for loss/metric curves and `results.csv` for per-epoch values. Evaluation prints its comparison folder. To use the trained weights with the robot:

```bash
python main.py --weights runs/objects_no_aug/weights/best.pt
```

Compare `objects_no_aug` and `objects_augmented` using the same dataset split, epochs, image size and evaluation confidence. Keep the existing run artifacts; repeated run names may be incremented.
