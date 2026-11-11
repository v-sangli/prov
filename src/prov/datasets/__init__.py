"""Layer 4: dataset versions, frozen lists of episode IDs (no bytes copied).
Imports core, storage, artifacts, episodes (below it).

members   member episodes of a version; {ses_id: [episode_index]} for LeRobot loading
split     train / holdout split by episode or by session
freeze    make `ds:<name>/<n>` (and `-train` / `-holdout`) from IDs or a catalog query
tables    catalog table: dataset_members
"""
