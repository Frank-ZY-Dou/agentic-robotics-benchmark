# NOTICE (grader-side; never staged into the agent's home)

Vehicle geometry, textures and part data: the benchmark owner's own tenth-scale car model and the CAD resources it was built from; the owner confirmed they may be redistributed with this task.

The cell's hidden kit (`tests/gt/`, unpacked at verify start from the asset dataset, or from the local development copy
`tests/assets/gt.tar.xz`) holds the car's visual meshes (decimated from the model, two product-label textures replaced
by unlabelled copies) and the simplified, subtract-only collision pieces made from the model's dimensions; the
differences between collision and appearance are documented to the agent in the cell manual.

The arm and the gripper are the MuJoCo Menagerie models `universal_robots_ur10e` (BSD-3-Clause) and `robotiq_2f85`
(BSD-2-Clause), commit c96a32d28fb5da84da38c1da4d749e7a13212855, with their licences in `given/robot/` (the files of the
benchmark's quadruped assembly task, `quadruped_full_assembly_12dof_ur10e`, unchanged); the cell mounts the gripper on
the real flange face (`arm/assembly_quad/ur_robot.py`) and drives the arm with its own computed-torque controller
(`ur_controller.py`). The cell's structure (a workbench with the base on a stand, the other parts loose on the bench or
in a tray, an industrial arm that builds the product, a coupling state machine per slot) follows the benchmark's
assembly tasks; their grader modules `arm/assembly_cell`, `assembly_info`, `assembly_six`, `assembly_quad`, `render`,
`render_filament`, `room`, `common`, `robotics_grader` are vendored here byte for byte, and `netguard.py` is the copy of
`driving_safety_supervisor`'s.

The agent cameras' scenery is the quadruped assembly task's baked factory hall and bench-top maps, unchanged (built
from the FactoryWarehouse Interior Modular Pack 1.0.1 (CyberneticWalrus) and the wall row of the Archviz Laboratory
Pack 2.0 (Unity Asset Store; licensed for redistribution; rebuilt without Unity), the bench top Poly Haven's
oak_veneer_01 (CC0)).

The givens, the instruction and the public card name neither the car platform the model follows nor its vendors or
the benchmark's model sources; this file carries the attribution.

## Where the files are, and their terms

The large givens (the units' part files, the drawings, the picture manual, the arm and gripper models and the cameras'
scenery) are served by the benchmark's asset dataset `grounded-intelligence-initiative/ale-robotics-assets` under
`tasks/driving/racecar_full_assembly_tenth_scale_ur10e/payload/`, at the commit pinned in `environment/assets.sha256`;
the hidden kit `gt.tar.xz` is `tasks/driving/racecar_full_assembly_tenth_scale_ur10e/verifier/gt.tar.xz` there, at the
commit pinned in `grader_config.json` (`hidden_gt.url`). The car model above is the same model of the maintainer's as
that of the sibling task `racecar_cad_design_from_requirements`, whose `tests/NOTICE.md` names the makers' CAD files it
holds: the photographs are renders of it, the part files and the kit's meshes are decimated from it, and what derives
from those makers' CAD files keeps their makers' terms. The arm and gripper models keep their BSD licences (their
LICENSE files next to them); the cameras' scenery keeps the terms named above. The dataset card's licence note says the
same.
