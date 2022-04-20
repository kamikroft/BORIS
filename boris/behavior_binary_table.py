"""
BORIS
Behavioral Observation Research Interactive Software
Copyright 2012-2022 Olivier Friard

  This program is free software; you can redistribute it and/or modify
  it under the terms of the GNU General Public License as published by
  the Free Software Foundation; either version 2 of the License, or
  (at your option) any later version.

  This program is distributed in the hope that it will be useful,
  but WITHOUT ANY WARRANTY; without even the implied warranty of
  MERCHANTABILITY or FITNESS FOR A PARTICULAR PURPOSE.  See the
  GNU General Public License for more details.

  You should have received a copy of the GNU General Public License
  along with this program; if not, write to the Free Software
  Foundation, Inc., 51 Franklin Street, Fifth Floor, Boston,
  MA 02110-1301, USA.
"""

import os
import pathlib
import re
import sys
from decimal import Decimal as dc
import logging

import tablib
from PyQt5.QtCore import Qt
from PyQt5.QtWidgets import QFileDialog, QInputDialog, QMessageBox

from . import dialog
from . import project_functions
from . import select_observations
from . import utilities as util
from . import config as cfg
from . import select_subj_behav


def create_behavior_binary_table(pj: dict, selected_observations: list, parameters_obs: dict,
                                 time_interval: float) -> dict:
    """
    create behavior binary table

    Args:
        pj (dict): project dictionary
        selected_observations (list): list of selected observations
        parameters_obs (dict): dcit of parameters
        time_interval (float): time interval (in seconds)

    Returns:
        dict: dictionary of tablib dataset

    """

    results_df = {}

    state_behavior_codes = [
        x for x in util.state_behavior_codes(pj[cfg.ETHOGRAM]) if x in parameters_obs[cfg.SELECTED_BEHAVIORS]
    ]
    point_behavior_codes = [
        x for x in util.point_behavior_codes(pj[cfg.ETHOGRAM]) if x in parameters_obs[cfg.SELECTED_BEHAVIORS]
    ]
    if not state_behavior_codes and not point_behavior_codes:
        return {"error": True, "msg": "No events selected"}

    for obs_id in selected_observations:

        start_time = parameters_obs[cfg.START_TIME]
        end_time = parameters_obs[cfg.END_TIME]

        # check observation interval
        if parameters_obs["time"] == cfg.TIME_FULL_OBS:
            max_obs_length, _ = project_functions.observation_length(pj, [obs_id])
            start_time = dc("0.000")
            end_time = dc(max_obs_length)

        if parameters_obs["time"] == cfg.TIME_EVENTS:

            try:
                start_time = dc(pj[cfg.OBSERVATIONS][obs_id][cfg.EVENTS][0][0])
            except Exception:
                start_time = dc("0.000")
            try:
                end_time = dc(pj[cfg.OBSERVATIONS][obs_id][cfg.EVENTS][-1][0])
            except Exception:
                max_obs_length, _ = project_functions.observation_length(pj, [obs_id])
                end_time = dc(max_obs_length)

        if obs_id not in results_df:
            results_df[obs_id] = {}

        for subject in parameters_obs[cfg.SELECTED_SUBJECTS]:

            # extract tuple (behavior, modifier)
            behav_modif_list = [(idx[2], idx[3]) for idx in pj[cfg.OBSERVATIONS][obs_id][cfg.EVENTS] if idx[1] == (
                subject if subject != cfg.NO_FOCAL_SUBJECT else "") and idx[2] in parameters_obs[cfg.SELECTED_BEHAVIORS]
                               ]

            # extract observed subjects NOT USED at the moment
            observed_subjects = [
                event[cfg.EVENT_SUBJECT_FIELD_IDX] for event in pj[cfg.OBSERVATIONS][obs_id][cfg.EVENTS]
            ]

            # add selected behavior if not found in (behavior, modifier)
            if not parameters_obs[cfg.EXCLUDE_BEHAVIORS]:
                # for behav in state_behavior_codes:
                for behav in parameters_obs[cfg.SELECTED_BEHAVIORS]:
                    if behav not in [x[0] for x in behav_modif_list]:
                        behav_modif_list.append((behav, ""))

            behav_modif_set = set(behav_modif_list)
            observed_behav = [(x[0], x[1]) for x in sorted(behav_modif_set)]
            if parameters_obs[cfg.INCLUDE_MODIFIERS]:
                results_df[obs_id][subject] = tablib.Dataset(
                    headers=["time"] + [f"{x[0]}" + f" ({x[1]})" * (x[1] != "") for x in sorted(behav_modif_set)])
            else:
                results_df[obs_id][subject] = tablib.Dataset(headers=["time"] + [x[0] for x in sorted(behav_modif_set)])

            if subject == cfg.NO_FOCAL_SUBJECT:
                sel_subject_dict = {"": {cfg.SUBJECT_NAME: ""}}
            else:
                sel_subject_dict = dict([(idx, pj[cfg.SUBJECTS][idx])
                                         for idx in pj[cfg.SUBJECTS]
                                         if pj[cfg.SUBJECTS][idx][cfg.SUBJECT_NAME] == subject])

            row_idx = 0
            t = start_time
            while t <= end_time:

                # state events
                current_states = util.get_current_states_modifiers_by_subject_2(
                    state_behavior_codes, pj[cfg.OBSERVATIONS][obs_id][cfg.EVENTS], sel_subject_dict, t)

                # point events
                current_point = util.get_current_points_by_subject(point_behavior_codes,
                                                                   pj[cfg.OBSERVATIONS][obs_id][cfg.EVENTS],
                                                                   sel_subject_dict, t, time_interval)

                cols = [float(t)]  # time

                for behav in observed_behav:
                    if behav[0] in state_behavior_codes:
                        cols.append(int(behav in current_states[list(current_states.keys())[0]]))

                    if behav[0] in point_behavior_codes:
                        cols.append(current_point[list(current_point.keys())[0]].count(behav))

                results_df[obs_id][subject].append(cols)

                t += time_interval
                row_idx += 1

    return results_df


def behavior_binary_table(self):
    """
    ask user for parameters for behavior binary table
    call create_behavior_binary_table
    """

    QMessageBox.warning(
        None,
        cfg.programName,
        ("Depending of the length of your observations "
         "the execution of this function may be very long.<br>"
         "The program interface may freeze, be patient. <br>"),
    )

    _, selected_observations = select_observations.select_observations(
        self.pj, cfg.MULTIPLE, "Select observations for the behavior binary table")

    if not selected_observations:
        return
    # check if state events are paired
    out = ""
    not_paired_obs_list = []
    for obs_id in selected_observations:
        r, msg = project_functions.check_state_events_obs(obs_id, self.pj[cfg.ETHOGRAM],
                                                          self.pj[cfg.OBSERVATIONS][obs_id])

        if not r:
            out += f"Observation: <strong>{obs_id}</strong><br>{msg}<br>"
            not_paired_obs_list.append(obs_id)

    if out:
        out = f"The observations with UNPAIRED state events will be removed from the analysis<br><br>{out}"
        results = dialog.Results_dialog()
        results.setWindowTitle(f"{cfg.programName} - Check selected observations")
        results.ptText.setReadOnly(True)
        results.ptText.appendHtml(out)
        results.pbSave.setVisible(False)
        results.pbCancel.setVisible(True)

        if not results.exec_():
            return
    selected_observations = [x for x in selected_observations if x not in not_paired_obs_list]
    if not selected_observations:
        return

    max_obs_length, _ = project_functions.observation_length(self.pj, selected_observations)
    if max_obs_length == -1:  # media length not available, user choose to not use events
        return

    parameters = select_subj_behav.choose_obs_subj_behav_category(
        self,
        selected_observations,
        maxTime=max_obs_length,
        flagShowIncludeModifiers=True,
        flagShowExcludeBehaviorsWoEvents=True,
        by_category=False,
    )

    if not parameters[cfg.SELECTED_SUBJECTS] or not parameters[cfg.SELECTED_BEHAVIORS]:
        QMessageBox.warning(None, cfg.programName, "Select subject(s) and behavior(s) to analyze")
        return

    # ask for time interval
    i, ok = QInputDialog.getDouble(None, "Behavior binary table", "Time interval (in seconds):", 1.0, 0.001, 86400, 3)
    if not ok:
        return
    time_interval = util.float2decimal(i)

    results_df = create_behavior_binary_table(self.pj, selected_observations, parameters, time_interval)

    if "error" in results_df:
        QMessageBox.warning(None, cfg.programName, results_df["msg"])
        return

    # save results
    if len(selected_observations) == 1:
        extended_file_formats = [
            "Tab Separated Values (*.tsv)",
            "Comma Separated Values (*.csv)",
            "Open Document Spreadsheet ODS (*.ods)",
            "Microsoft Excel Spreadsheet XLSX (*.xlsx)",
            "Legacy Microsoft Excel Spreadsheet XLS (*.xls)",
            "HTML (*.html)",
        ]
        file_formats = ["tsv", "csv", "ods", "xlsx", "xls", "html"]

        file_name, filter_ = QFileDialog().getSaveFileName(None, "Save results", "", ";;".join(extended_file_formats))
        if not file_name:
            return

        output_format = file_formats[extended_file_formats.index(filter_)]

        if pathlib.Path(file_name).suffix != "." + output_format:
            file_name = str(pathlib.Path(file_name)) + "." + output_format
            # check if file with new extension already exists
            if pathlib.Path(file_name).is_file():
                if (dialog.MessageDialog(cfg.programName, f"The file {file_name} already exists.",
                                         [cfg.CANCEL, cfg.OVERWRITE]) == cfg.CANCEL):
                    return
    else:
        items = (
            "Tab Separated Values (*.tsv)",
            "Comma separated values (*.csv)",
            "Open Document Spreadsheet (*.ods)",
            "Microsoft Excel Spreadsheet XLSX (*.xlsx)",
            "Legacy Microsoft Excel Spreadsheet XLS (*.xls)",
            "HTML (*.html)",
        )

        item, ok = QInputDialog.getItem(None, "Save results", "Available formats", items, 0, False)
        if not ok:
            return
        output_format = re.sub(".* \(\*\.", "", item)[:-1]

        export_dir = QFileDialog().getExistingDirectory(None,
                                                        "Choose a directory to save results",
                                                        os.path.expanduser("~"),
                                                        options=QFileDialog.ShowDirsOnly)
        if not export_dir:
            return

    mem_command = ""
    for obs_id in results_df:

        for subject in results_df[obs_id]:

            if len(selected_observations) > 1:
                file_name_with_subject = (str(pathlib.Path(export_dir) / util.safeFileName(obs_id + "_" + subject)) +
                                          "." + output_format)
            else:
                file_name_with_subject = (str(os.path.splitext(file_name)[0] + util.safeFileName("_" + subject)) + "." +
                                          output_format)

            # check if file with new extension already exists
            if mem_command != cfg.OVERWRITE_ALL and pathlib.Path(file_name_with_subject).is_file():
                if mem_command == "Skip all":
                    continue
                mem_command = dialog.MessageDialog(
                    cfg.programName,
                    f"The file {file_name_with_subject} already exists.",
                    [cfg.OVERWRITE, cfg.OVERWRITE_ALL, "Skip", "Skip all", cfg.CANCEL],
                )
                if mem_command == cfg.CANCEL:
                    return
                if mem_command in ["Skip", "Skip all"]:
                    continue

            try:
                if output_format in ["csv", "tsv", "html"]:
                    with open(file_name_with_subject, "wb") as f:
                        f.write(str.encode(results_df[obs_id][subject].export(output_format)))

                if output_format in ["ods", "xlsx", "xls"]:
                    with open(file_name_with_subject, "wb") as f:
                        f.write(results_df[obs_id][subject].export(output_format))

            except Exception:

                error_type, error_file_name, error_lineno = util.error_info(sys.exc_info())
                logging.critical(
                    f"Error in behavior binary table function: {error_type} {error_file_name} {error_lineno}")

                QMessageBox.critical(None, cfg.programName, f"Error saving file: {error_type}")
                return
