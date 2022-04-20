"""
BORIS
Behavioral Observation Research Interactive Software
Copyright 2012-2022 Olivier Friard

This file is part of BORIS.

  BORIS is free software; you can redistribute it and/or modify
  it under the terms of the GNU General Public License as published by
  the Free Software Foundation; either version 3 of the License, or
  any later version.

  BORIS is distributed in the hope that it will be useful,
  but WITHOUT ANY WARRANTY; without even the implied warranty of
  MERCHANTABILITY or FITNESS FOR A PARTICULAR PURPOSE.  See the
  GNU General Public License for more details.

  You should have received a copy of the GNU General Public License
  along with this program; if not see <http://www.gnu.org/licenses/>.

"""

import logging
import os
import re
import tablib
from decimal import Decimal
import pathlib as pl

from . import observation_operations

from . import utilities as util
from . import project_functions
from . import select_subj_behav
from . import dialog
from . import config as cfg
from . import gui_utilities
from . import db_functions
from . import time_budget_functions
from . import select_observations

from PyQt5.QtWidgets import (QPushButton, QSpacerItem, QHBoxLayout, QTableWidget, QListWidget, QVBoxLayout, QLabel,
                             QSizePolicy, QWidget, QFileDialog, QTableWidgetItem, QInputDialog)
from PyQt5.QtCore import Qt


class timeBudgetResults(QWidget):
    """
    class for displaying time budget results in new window
    a function for exporting data in TSV, CSV, XLS and ODS formats is implemented

    Args:
        pj (dict): BORIS project
    """

    def __init__(self, pj, config_param):
        super().__init__()

        self.pj = pj
        self.config_param = config_param

        hbox = QVBoxLayout(self)

        self.label = QLabel("")
        hbox.addWidget(self.label)

        self.lw = QListWidget()
        # self.lw.setEnabled(False)
        self.lw.setMaximumHeight(100)
        hbox.addWidget(self.lw)

        self.lbTotalObservedTime = QLabel("")
        hbox.addWidget(self.lbTotalObservedTime)

        # behaviors excluded from total time
        self.excluded_behaviors_list = QLabel("")
        hbox.addWidget(self.excluded_behaviors_list)

        self.twTB = QTableWidget()
        hbox.addWidget(self.twTB)

        hbox2 = QHBoxLayout()

        self.pbSave = QPushButton("Save results", clicked=self.pbSave_clicked)
        hbox2.addWidget(self.pbSave)

        spacerItem = QSpacerItem(241, 20, QSizePolicy.Expanding, QSizePolicy.Minimum)
        hbox2.addItem(spacerItem)

        self.pbClose = QPushButton("Close", clicked=self.close_clicked)
        hbox2.addWidget(self.pbClose)

        hbox.addLayout(hbox2)

        self.setWindowTitle("Time budget")

    def close_clicked(self):
        """
        save geometry of widget and close it
        """
        gui_utilities.save_geometry(self, "time budget")
        self.close()

    def pbSave_clicked(self):
        """
        save time budget analysis results in TSV, CSV, ODS, XLS format
        """

        def complete(l: list, max_: int) -> list:
            """
            complete list with empty string until len = max

            Args:
                l (list): list to complete
                max_ (int): length of the returned list

            Returns:
                list: completed list
            """

            while len(l) < max_:
                l.append("")
            return l

        logging.debug("save time budget results to file")

        extended_file_formats = [
            "Tab Separated Values (*.tsv)",
            "Comma Separated Values (*.csv)",
            "Open Document Spreadsheet ODS (*.ods)",
            "Microsoft Excel Spreadsheet XLSX (*.xlsx)",
            "Legacy Microsoft Excel Spreadsheet XLS (*.xls)",
            "HTML (*.html)",
        ]
        file_formats = ["tsv", "csv", "ods", "xlsx", "xls", "html"]

        file_name, filter_ = QFileDialog().getSaveFileName(self, "Save Time budget analysis", "",
                                                           ";;".join(extended_file_formats))

        if not file_name:
            return

        outputFormat = file_formats[extended_file_formats.index(filter_)]
        if pl.Path(file_name).suffix != "." + outputFormat:
            file_name = str(pl.Path(file_name)) + "." + outputFormat
            # check if file with new extension already exists
            if pl.Path(file_name).is_file():
                if (dialog.MessageDialog(cfg.programName, f"The file {file_name} already exists.",
                                         [cfg.CANCEL, cfg.OVERWRITE]) == cfg.CANCEL):
                    return

        rows = []

        # 1 observation
        if (self.lw.count() == 1 and self.config_param.get(cfg.TIME_BUDGET_FORMAT, cfg.DEFAULT_TIME_BUDGET_FORMAT)
                == cfg.COMPACT_TIME_BUDGET_FORMAT):
            col1, indep_var_label = [], []
            # add obs id
            col1.append(self.lw.item(0).text())
            # add obs date
            col1.append(self.pj[cfg.OBSERVATIONS][self.lw.item(0).text()].get("date", ""))

            # description
            col1.append(util.eol2space(self.pj[cfg.OBSERVATIONS][self.lw.item(0).text()].get(cfg.DESCRIPTION, "")))
            header = ["Observation id", "Observation date", "Description"]

            # indep var
            for var in self.pj[cfg.OBSERVATIONS][self.lw.item(0).text()].get(cfg.INDEPENDENT_VARIABLES, {}):
                indep_var_label.append(var)
                col1.append(self.pj[cfg.OBSERVATIONS][self.lw.item(0).text()][cfg.INDEPENDENT_VARIABLES][var])

            header.extend(indep_var_label)

            col1.extend([f"{self.min_time:0.3f}", f"{self.max_time:0.3f}", f"{self.max_time - self.min_time:0.3f}"])
            header.extend(["Time budget start", "Time budget stop", "Time budget duration"])

            for col_idx in range(self.twTB.columnCount()):
                header.append(self.twTB.horizontalHeaderItem(col_idx).text())
            rows.append(header)

            for row_idx in range(self.twTB.rowCount()):
                values = []
                for col_idx in range(self.twTB.columnCount()):
                    values.append(util.intfloatstr(self.twTB.item(row_idx, col_idx).text()))
                rows.append(col1 + values)

        else:
            # observations list
            rows.append(["Observations:"])
            for idx in range(self.lw.count()):
                rows.append([""])
                rows.append(["Observation id", self.lw.item(idx).text()])
                rows.append(["Observation date", self.pj[cfg.OBSERVATIONS][self.lw.item(idx).text()].get("date", "")])
                rows.append([
                    "Description",
                    util.eol2space(self.pj[cfg.OBSERVATIONS][self.lw.item(idx).text()].get(cfg.DESCRIPTION, "")),
                ])

                if cfg.INDEPENDENT_VARIABLES in self.pj[cfg.OBSERVATIONS][self.lw.item(idx).text()]:
                    rows.append(["Independent variables:"])
                    for var in self.pj[cfg.OBSERVATIONS][self.lw.item(idx).text()][cfg.INDEPENDENT_VARIABLES]:
                        rows.append(
                            [var, self.pj[cfg.OBSERVATIONS][self.lw.item(idx).text()][cfg.INDEPENDENT_VARIABLES][var]])

            if self.excluded_behaviors_list.text():
                s1, s2 = self.excluded_behaviors_list.text().split(": ")
                rows.extend([[""], [s1] + s2.split(", ")])

            rows.extend([[""], [""], ["Time budget:"]])

            # write header
            header = []
            for col_idx in range(self.twTB.columnCount()):
                header.append(self.twTB.horizontalHeaderItem(col_idx).text())

            rows.append(header)
            rows.append([""])

            for row in range(self.twTB.rowCount()):
                values = []
                for col_idx in range(self.twTB.columnCount()):
                    values.append(util.intfloatstr(self.twTB.item(row, col_idx).text()))

                rows.append(values)

        max_row_length = max([len(r) for r in rows])
        data = tablib.Dataset()
        data.title = "Time budget"

        for row in rows:
            data.append(complete(row, max_row_length))

        if outputFormat in ["tsv", "csv", "html"]:
            with open(file_name, "wb") as f:
                f.write(str.encode(data.export(outputFormat)))
            return

        if outputFormat in ["ods", "xlsx", "xls"]:
            with open(file_name, "wb") as f:
                f.write(data.export(outputFormat))
            return


def time_budget(self, mode: str, mode2: str = "list"):
    """
    time budget (by behavior or category)

    Args:
        mode (str): ["by_behavior", "by_category"]
        mode2 (str): must be in ["list", "current"]
    """

    if mode2 == "current" and self.observationId:
        selectedObservations = [self.observationId]
    if mode2 == "list":
        _, selectedObservations = select_observations.select_observations(self.pj, mode=cfg.MULTIPLE, windows_title="")

        if not selectedObservations:
            return

    # check if coded behaviors are defined in ethogram
    ethogram_behavior_codes = {self.pj[cfg.ETHOGRAM][idx][cfg.BEHAVIOR_CODE] for idx in self.pj[cfg.ETHOGRAM]}
    behaviors_not_defined = []
    out = ""  # will contain the output
    for obs_id in selectedObservations:
        for event in self.pj[cfg.OBSERVATIONS][obs_id][cfg.EVENTS]:
            if event[cfg.EVENT_BEHAVIOR_FIELD_IDX] not in ethogram_behavior_codes:
                behaviors_not_defined.append(event[cfg.EVENT_BEHAVIOR_FIELD_IDX])
    if set(sorted(behaviors_not_defined)):
        out += ("The following behaviors are not defined in the ethogram: "
                f"<b>{', '.join(set(sorted(behaviors_not_defined)))}</b><br><br>")

    # check if state events are paired
    not_paired_obs_list = []
    for obs_id in selectedObservations:
        r, msg = project_functions.check_state_events_obs(obs_id, self.pj[cfg.ETHOGRAM],
                                                          self.pj[cfg.OBSERVATIONS][obs_id], self.timeFormat)

        if not r:
            out += f"Observation: <strong>{obs_id}</strong><br>{msg}<br>"
            not_paired_obs_list.append(obs_id)

    if out:
        out = f"Some selected observations have issues:<br><br>{out}"
        self.results = dialog.Results_dialog()
        self.results.setWindowTitle(f"{cfg.programName} - Check selected observations")
        self.results.ptText.setReadOnly(True)
        self.results.ptText.appendHtml(out)
        self.results.pbSave.setVisible(False)
        self.results.pbCancel.setVisible(True)

        if not self.results.exec_():
            return

    flagGroup = False
    if len(selectedObservations) > 1:
        flagGroup = (dialog.MessageDialog(cfg.programName, "Group observations in one time budget analysis?",
                                          [cfg.YES, cfg.NO]) == cfg.YES)

    max_obs_length, selectedObsTotalMediaLength = observation_operations.observation_length(self, selectedObservations)
    if max_obs_length == -1:  # media length not available, user choose to not use events
        return

    logging.debug(f"max_obs_length: {max_obs_length}, selectedObsTotalMediaLength: {selectedObsTotalMediaLength}")

    parameters = select_subj_behav.choose_obs_subj_behav_category(
        self,
        selectedObservations,
        maxTime=max_obs_length if len(selectedObservations) > 1 else selectedObsTotalMediaLength,
        by_category=(mode == "by_category"),
    )

    if not parameters[cfg.SELECTED_SUBJECTS] or not parameters[cfg.SELECTED_BEHAVIORS]:
        return

    # ask for excluding behaviors durations from total time
    cancel_pressed, parameters[cfg.EXCLUDED_BEHAVIORS] = self.filter_behaviors(
        title="Select behaviors to exclude",
        text=("The duration of the selected behaviors will "
              "be subtracted from the total time"),
        table="",
        behavior_type=[cfg.STATE_EVENT],
    )
    if cancel_pressed:
        return

    # check if time_budget window must be used
    if flagGroup or len(selectedObservations) == 1:

        cursor = db_functions.load_events_in_db(
            self.pj,
            parameters[cfg.SELECTED_SUBJECTS],
            selectedObservations,
            parameters[cfg.SELECTED_BEHAVIORS],
            time_interval=cfg.TIME_FULL_OBS,
        )

        total_observation_time = 0
        for obsId in selectedObservations:

            obs_length = project_functions.observation_total_length(self.pj[cfg.OBSERVATIONS][obsId])

            if obs_length == Decimal("-1"):  # media length not available
                parameters[cfg.TIME_INTERVAL] = cfg.TIME_EVENTS

            if parameters[cfg.TIME_INTERVAL] == cfg.TIME_FULL_OBS:
                min_time = float(0)
                # check if the last event is recorded after media file length
                try:
                    if float(self.pj[cfg.OBSERVATIONS][obsId][cfg.EVENTS][-1][0]) > float(obs_length):
                        max_time = float(self.pj[cfg.OBSERVATIONS][obsId][cfg.EVENTS][-1][0])
                    else:
                        max_time = float(obs_length)
                except Exception:
                    max_time = float(obs_length)

            if parameters[cfg.TIME_INTERVAL] == cfg.TIME_EVENTS:
                try:
                    min_time = float(self.pj[cfg.OBSERVATIONS][obsId][cfg.EVENTS][0][0])  # first event
                except Exception:
                    min_time = float(0)
                try:
                    max_time = float(self.pj[cfg.OBSERVATIONS][obsId][cfg.EVENTS][-1][0])  # last event
                except Exception:
                    max_time = float(obs_length)

            if parameters[cfg.TIME_INTERVAL] == cfg.TIME_ARBITRARY_INTERVAL:
                min_time = float(parameters[cfg.START_TIME])
                max_time = float(parameters[cfg.END_TIME])

                # check intervals
                for subj in parameters[cfg.SELECTED_SUBJECTS]:
                    for behav in parameters[cfg.SELECTED_BEHAVIORS]:
                        if cfg.POINT in self.eventType(behav).upper():
                            continue
                        # extract modifiers

                        cursor.execute(
                            "SELECT distinct modifiers FROM events WHERE observation = ? AND subject = ? AND code = ?",
                            (obsId, subj, behav),
                        )
                        distinct_modifiers = list(cursor.fetchall())

                        # logging.debug("distinct_modifiers: {}".format(distinct_modifiers))

                        for modifier in distinct_modifiers:

                            # logging.debug("modifier #{}#".format(modifier[0]))

                            # insert events at boundaries of time interval
                            if (len(
                                    cursor.execute(
                                        ("SELECT * FROM events "
                                         "WHERE observation = ? AND subject = ? AND code = ? AND modifiers = ? "
                                         "AND occurence < ?"),
                                        (obsId, subj, behav, modifier[0], min_time),
                                    ).fetchall()) % 2):

                                cursor.execute(
                                    ("INSERT INTO events (observation, subject, code, type, modifiers, occurence) "
                                     "VALUES (?,?,?,?,?,?)"),
                                    (obsId, subj, behav, "STATE", modifier[0], min_time),
                                )

                            if (len(
                                    cursor.execute(
                                        ("SELECT * FROM events WHERE observation = ? AND subject = ? AND code = ? "
                                         "AND modifiers = ? AND occurence > ?"),
                                        (obsId, subj, behav, modifier[0], max_time),
                                    ).fetchall()) % 2):

                                cursor.execute(
                                    ("INSERT INTO events (observation, subject, code, type, modifiers, occurence) "
                                     "VALUES (?,?,?,?,?,?)"),
                                    (obsId, subj, behav, "STATE", modifier[0], max_time),
                                )
                        try:
                            cursor.execute("COMMIT")
                        except Exception:
                            pass

            total_observation_time += max_time - min_time

            # delete all events out of time interval from db
            cursor.execute(
                "DELETE FROM events WHERE observation = ? AND (occurence < ? OR occurence > ?)",
                (obsId, min_time, max_time),
            )

        out, categories = time_budget_functions.time_budget_analysis(self.pj[cfg.ETHOGRAM],
                                                                     cursor,
                                                                     selectedObservations,
                                                                     parameters,
                                                                     by_category=(mode == "by_category"))

        # check excluded behaviors
        excl_behaviors_total_time = {}
        for element in out:
            if element["subject"] not in excl_behaviors_total_time:
                excl_behaviors_total_time[element["subject"]] = 0
            if element["behavior"] in parameters[cfg.EXCLUDED_BEHAVIORS]:
                excl_behaviors_total_time[element["subject"]] += (element["duration"]
                                                                  if not isinstance(element["duration"], str) else 0)

        # widget for results visualization
        self.tb = timeBudgetResults(self.pj, self.config_param)

        # add min and max time
        self.tb.min_time = min_time
        self.tb.max_time = max_time

        # observations list
        self.tb.label.setText("Selected observations")
        for obs_id in selectedObservations:
            # self.tb.lw.addItem(f"{obs_id}  {self.pj[OBSERVATIONS][obs_id]['date']}  {self.pj[OBSERVATIONS][obs_id]['description']}")
            self.tb.lw.addItem(obs_id)

        # media length
        if len(selectedObservations) > 1:
            if total_observation_time:
                if self.timeFormat == cfg.HHMMSS:
                    self.tb.lbTotalObservedTime.setText(
                        f"Total observation length: {util.seconds2time(total_observation_time)}")
                if self.timeFormat == cfg.S:
                    self.tb.lbTotalObservedTime.setText(
                        f"Total observation length: {float(total_observation_time):0.3f}")
            else:
                self.tb.lbTotalObservedTime.setText("Total observation length: not available")
        else:
            if self.timeFormat == cfg.HHMMSS:
                self.tb.lbTotalObservedTime.setText(
                    f"Analysis from {util.seconds2time(min_time)} to {util.seconds2time(max_time)}")
            if self.timeFormat == cfg.S:
                self.tb.lbTotalObservedTime.setText(f"Analysis from {float(min_time):0.3f} to {float(max_time):0.3f} s")

        # behaviors excluded from total time
        if parameters[cfg.EXCLUDED_BEHAVIORS]:
            self.tb.excluded_behaviors_list.setText("Behaviors excluded from total time: " +
                                                    (", ".join(parameters[cfg.EXCLUDED_BEHAVIORS])))
        else:
            self.tb.excluded_behaviors_list.setVisible(False)

        if mode == "by_behavior":

            tb_fields = [
                "Subject",
                "Behavior",
                "Modifiers",
                "Total number of occurences",
                "Total duration (s)",
                "Duration mean (s)",
                "Duration std dev",
                "inter-event intervals mean (s)",
                "inter-event intervals std dev",
                "% of total length",
            ]
            fields = [
                "subject",
                "behavior",
                "modifiers",
                "number",
                "duration",
                "duration_mean",
                "duration_stdev",
                "inter_duration_mean",
                "inter_duration_stdev",
            ]

            self.tb.twTB.setColumnCount(len(tb_fields))
            self.tb.twTB.setHorizontalHeaderLabels(tb_fields)

            for row in out:
                self.tb.twTB.setRowCount(self.tb.twTB.rowCount() + 1)
                column = 0
                for field in fields:
                    """
                    if field == "duration":
                        item = QTableWidgetItem("{:0.3f}".format(row[field]))
                    else:
                    """
                    item = QTableWidgetItem(str(row[field]).replace(" ()", ""))
                    # no modif allowed
                    item.setFlags(Qt.ItemIsEnabled)
                    self.tb.twTB.setItem(self.tb.twTB.rowCount() - 1, column, item)
                    column += 1

                # % of total time
                if row["duration"] in [0, cfg.NA]:
                    item = QTableWidgetItem(str(row["duration"]))
                elif row["duration"] not in ["-", cfg.UNPAIRED] and selectedObsTotalMediaLength:
                    tot_time = float(total_observation_time)
                    # substract time of excluded behaviors from the total for the subject
                    if (row["subject"] in excl_behaviors_total_time and
                            row["behavior"] not in parameters[cfg.EXCLUDED_BEHAVIORS]):
                        tot_time -= excl_behaviors_total_time[row["subject"]]
                    item = QTableWidgetItem(str(round(row["duration"] / tot_time * 100, 1)) if tot_time > 0 else "-")
                else:
                    item = QTableWidgetItem("-")

                item.setFlags(Qt.ItemIsEnabled)
                self.tb.twTB.setItem(self.tb.twTB.rowCount() - 1, column, item)

        if mode == "by_category":

            tb_fields = ["Subject", "Category", "Total number", "Total duration (s)"]
            fields = ["number", "duration"]

            self.tb.twTB.setColumnCount(len(tb_fields))
            self.tb.twTB.setHorizontalHeaderLabels(tb_fields)

            for subject in categories:

                for category in categories[subject]:

                    self.tb.twTB.setRowCount(self.tb.twTB.rowCount() + 1)

                    column = 0
                    item = QTableWidgetItem(subject)
                    item.setFlags(Qt.ItemIsEnabled)
                    self.tb.twTB.setItem(self.tb.twTB.rowCount() - 1, column, item)

                    column = 1
                    if category == "":
                        item = QTableWidgetItem("No category")
                    else:
                        item = QTableWidgetItem(category)
                    item.setFlags(Qt.ItemIsEnabled)
                    self.tb.twTB.setItem(self.tb.twTB.rowCount() - 1, column, item)

                    for field in fields:
                        column += 1

                        if field == "duration":
                            try:
                                item = QTableWidgetItem("{:0.3f}".format(categories[subject][category][field]))
                            except Exception:
                                item = QTableWidgetItem(categories[subject][category][field])
                        else:
                            item = QTableWidgetItem(str(categories[subject][category][field]))
                        item.setFlags(Qt.ItemIsEnabled)
                        item.setTextAlignment(Qt.AlignRight | Qt.AlignVCenter)
                        self.tb.twTB.setItem(self.tb.twTB.rowCount() - 1, column, item)

        self.tb.twTB.resizeColumnsToContents()

        gui_utilities.restore_geometry(self.tb, "time budget", (0, 0))

        self.tb.show()

    if len(selectedObservations) > 1 and not flagGroup:

        items = (
            "Tab Separated Values (*.tsv)",
            "Comma separated values (*.csv)",
            "OpenDocument Spreadsheet (*.ods)",
            "OpenDocument Workbook (*.ods)",
            "Microsoft Excel Spreadsheet (*.xlsx)",
            "Microsoft Excel Workbook (*.xlsx)",
            "HTML (*.html)",
            "Legacy Microsoft Excel Spreadsheet (*.xls)",
        )

        formats = [
            "tsv",
            "csv",
            "od spreadsheet",
            "od workbook",
            "xlsx spreadsheet",
            "xlsx workbook",
            "html",
            "xls legacy",
        ]

        item, ok = QInputDialog.getItem(self, "Time budget analysis format", "Available formats", items, 0, False)
        if not ok:
            return

        outputFormat = formats[items.index(item)]
        extension = re.sub(".* \(\*\.", "", item)[:-1]

        flagWorkBook = False

        if "workbook" in outputFormat:
            workbook = tablib.Databook()
            flagWorkBook = True
            if "xls" in outputFormat:
                filters = "Microsoft Excel Workbook *.xlsx (*.xlsx);;All files (*)"
            if "od" in outputFormat:
                filters = "Open Document Workbook *.ods (*.ods);;All files (*)"

            WBfileName, filter_ = QFileDialog(self).getSaveFileName(self, "Save Time budget analysis", "", filters)
            if not WBfileName:
                return

        else:  # not workbook
            exportDir = QFileDialog(self).getExistingDirectory(
                self,
                "Choose a directory to save the time budget analysis",
                os.path.expanduser("~"),
                options=QFileDialog.ShowDirsOnly,
            )
            if not exportDir:
                return

        if mode == "by_behavior":

            tb_fields = [
                "Subject",
                "Behavior",
                "Modifiers",
                "Total number of occurences",
                "Total duration (s)",
                "Duration mean (s)",
                "Duration std dev",
                "inter-event intervals mean (s)",
                "inter-event intervals std dev",
                "% of total length",
            ]
            fields = [
                "subject",
                "behavior",
                "modifiers",
                "number",
                "duration",
                "duration_mean",
                "duration_stdev",
                "inter_duration_mean",
                "inter_duration_stdev",
            ]

        if mode == "by_category":

            tb_fields = ["Subject", "Category", "Total number of occurences", "Total duration (s)"]
            fields = ["subject", "category", "number", "duration"]

        mem_command = ""
        for obsId in selectedObservations:

            cursor = db_functions.load_events_in_db(self.pj, parameters[cfg.SELECTED_SUBJECTS], [obsId],
                                                    parameters[cfg.SELECTED_BEHAVIORS])

            obs_length = project_functions.observation_total_length(self.pj[cfg.OBSERVATIONS][obsId])

            if obs_length == -1:
                obs_length = 0

            if parameters["time"] == cfg.TIME_FULL_OBS:
                min_time = float(0)
                # check if the last event is recorded after media file length
                try:
                    if float(self.pj[cfg.OBSERVATIONS][obsId][cfg.EVENTS][-1][0]) > float(obs_length):
                        max_time = float(self.pj[cfg.OBSERVATIONS][obsId][cfg.EVENTS][-1][0])
                    else:
                        max_time = float(obs_length)
                except Exception:
                    max_time = float(obs_length)

            if parameters["time"] == cfg.TIME_EVENTS:
                try:
                    min_time = float(self.pj[cfg.OBSERVATIONS][obsId][cfg.EVENTS][0][0])
                except Exception:
                    min_time = float(0)
                try:
                    max_time = float(self.pj[cfg.OBSERVATIONS][obsId][cfg.EVENTS][-1][0])
                except Exception:
                    max_time = float(obs_length)

            if parameters["time"] == cfg.TIME_ARBITRARY_INTERVAL:
                min_time = float(parameters[cfg.START_TIME])
                max_time = float(parameters[cfg.END_TIME])

                # check intervals
                for subj in parameters[cfg.SELECTED_SUBJECTS]:
                    for behav in parameters[cfg.SELECTED_BEHAVIORS]:
                        if cfg.POINT in project_functions.event_type(
                                behav, self.pj[cfg.ETHOGRAM]):  # self.eventType(behav).upper():
                            continue
                        # extract modifiers
                        # if plot_parameters["include modifiers"]:

                        cursor.execute(
                            "SELECT distinct modifiers FROM events WHERE observation = ? AND subject = ? AND code = ?",
                            (obsId, subj, behav),
                        )
                        distinct_modifiers = list(cursor.fetchall())

                        for modifier in distinct_modifiers:

                            if (len(
                                    cursor.execute(
                                        ("SELECT * FROM events "
                                         "WHERE observation = ? AND subject = ? "
                                         "AND code = ? AND modifiers = ? AND occurence < ?"),
                                        (obsId, subj, behav, modifier[0], min_time),
                                    ).fetchall()) % 2):
                                cursor.execute(
                                    ("INSERT INTO events (observation, subject, code, type, modifiers, occurence) "
                                     "VALUES (?,?,?,?,?,?)"),
                                    (obsId, subj, behav, "STATE", modifier[0], min_time),
                                )
                            if (len(
                                    cursor.execute(
                                        ("SELECT * FROM events WHERE observation = ? AND subject = ? AND code = ?"
                                         " AND modifiers = ? AND occurence > ?"),
                                        (obsId, subj, behav, modifier[0], max_time),
                                    ).fetchall()) % 2):
                                cursor.execute(
                                    ("INSERT INTO events (observation, subject, code, type, modifiers, occurence) "
                                     "VALUES (?,?,?,?,?,?)"),
                                    (obsId, subj, behav, cfg.STATE, modifier[0], max_time),
                                )
                        try:
                            cursor.execute("COMMIT")
                        except Exception:
                            pass

            cursor.execute(
                "DELETE FROM events WHERE observation = ? AND (occurence < ? OR occurence > ?)",
                (obsId, min_time, max_time),
            )

            out, categories = time_budget_functions.time_budget_analysis(self.pj[cfg.ETHOGRAM],
                                                                         cursor, [obsId],
                                                                         parameters,
                                                                         by_category=(mode == "by_category"))

            # check excluded behaviors
            excl_behaviors_total_time = {}
            for element in out:
                if element["subject"] not in excl_behaviors_total_time:
                    excl_behaviors_total_time[element["subject"]] = 0
                if element["behavior"] in parameters[cfg.EXCLUDED_BEHAVIORS]:
                    excl_behaviors_total_time[element["subject"]] += (element["duration"]
                                                                      if element["duration"] != "NA" else 0)

            # compact format
            if (self.config_param.get(cfg.TIME_BUDGET_FORMAT,
                                      cfg.DEFAULT_TIME_BUDGET_FORMAT) == cfg.COMPACT_TIME_BUDGET_FORMAT):
                rows = []
                col1 = []
                # observation id
                col1.append(obsId)
                col1.append(self.pj[cfg.OBSERVATIONS][obsId].get("date", ""))
                col1.append(util.eol2space(self.pj[cfg.OBSERVATIONS][obsId].get(cfg.DESCRIPTION, "")))
                header = ["Observation id", "Observation date", "Description"]

                indep_var_label = []
                indep_var_values = []
                if cfg.INDEPENDENT_VARIABLES in self.pj and self.pj[cfg.INDEPENDENT_VARIABLES]:
                    for idx in self.pj[cfg.INDEPENDENT_VARIABLES]:
                        indep_var_label.append(self.pj[cfg.INDEPENDENT_VARIABLES][idx]["label"])

                        if (cfg.INDEPENDENT_VARIABLES in self.pj[cfg.OBSERVATIONS][obsId] and
                                self.pj[cfg.INDEPENDENT_VARIABLES][idx]["label"]
                                in self.pj[cfg.OBSERVATIONS][obsId][cfg.INDEPENDENT_VARIABLES]):
                            indep_var_values.append(self.pj[cfg.OBSERVATIONS][obsId][cfg.INDEPENDENT_VARIABLES][self.pj[
                                cfg.INDEPENDENT_VARIABLES][idx]["label"]])

                header.extend(indep_var_label)
                col1.extend(indep_var_values)

                # interval analysis
                col1.extend([f"{min_time:0.3f}", f"{max_time:0.3f}", f"{max_time - min_time:0.3f}"])
                header.extend(["Time budget start", "Time budget stop", "Time budget duration"])

                if mode == "by_behavior":

                    # header
                    rows.append(header + tb_fields)

                    for row in out:
                        values = []
                        for field in fields:
                            values.append(str(row[field]).replace(" ()", ""))
                        # % of total time
                        if row["duration"] in [0, cfg.NA]:
                            values.append(row["duration"])
                        elif row["duration"] not in ["-", cfg.UNPAIRED] and selectedObsTotalMediaLength:
                            tot_time = float(max_time - min_time)
                            # substract duration of excluded behaviors from total time for each subject
                            if (row["subject"] in excl_behaviors_total_time and
                                    row["behavior"] not in parameters[cfg.EXCLUDED_BEHAVIORS]):
                                tot_time -= excl_behaviors_total_time[row["subject"]]
                            # % of tot time
                            values.append(round(row["duration"] / tot_time * 100, 1) if tot_time > 0 else "-")
                        else:
                            values.append("-")

                        rows.append(col1 + values)

                if mode == "by_category":
                    rows.append(header + tb_fields)

                    for subject in categories:

                        for category in categories[subject]:
                            values = []
                            values.append(subject)
                            if category == "":
                                values.append("No category")
                            else:
                                values.append(category)

                            values.append(categories[subject][category]["number"])
                            try:
                                values.append(f"{categories[subject][category]['duration']:0.3f}")
                            except Exception:
                                values.append(categories[subject][category]["duration"])

                            rows.append(col1 + values)

            # long format
            if (self.config_param.get(cfg.TIME_BUDGET_FORMAT,
                                      cfg.DEFAULT_TIME_BUDGET_FORMAT) == cfg.LONG_TIME_BUDGET_FORMAT):

                rows = []
                # observation id
                rows.append(["Observation id", obsId])
                rows.append([""])

                labels = ["Independent variables"]
                values = [""]
                if cfg.INDEPENDENT_VARIABLES in self.pj and self.pj[cfg.INDEPENDENT_VARIABLES]:
                    for idx in self.pj[cfg.INDEPENDENT_VARIABLES]:
                        labels.append(self.pj[cfg.INDEPENDENT_VARIABLES][idx]["label"])

                        if (cfg.INDEPENDENT_VARIABLES in self.pj[cfg.OBSERVATIONS][obsId] and
                                self.pj[cfg.INDEPENDENT_VARIABLES][idx]["label"]
                                in self.pj[cfg.OBSERVATIONS][obsId][cfg.INDEPENDENT_VARIABLES]):
                            values.append(self.pj[cfg.OBSERVATIONS][obsId][cfg.INDEPENDENT_VARIABLES][self.pj[
                                cfg.INDEPENDENT_VARIABLES][idx]["label"]])

                rows.append(labels)
                rows.append(values)
                rows.append([""])

                rows.append(["Analysis from", f"{min_time:0.3f}", "to", f"{max_time:0.3f}"])
                rows.append(["Total length (s)", f"{max_time - min_time:0.3f}"])
                rows.append([""])
                rows.append(["Time budget"])

                if mode == "by_behavior":

                    rows.append(tb_fields)

                    for row in out:
                        values = []
                        for field in fields:
                            values.append(str(row[field]).replace(" ()", ""))
                        # % of total time
                        if row["duration"] in [0, cfg.NA]:
                            values.append(row["duration"])
                        elif row["duration"] not in ["-", cfg.UNPAIRED] and selectedObsTotalMediaLength:
                            tot_time = float(max_time - min_time)
                            # substract duration of excluded behaviors from total time for each subject
                            if (row["subject"] in excl_behaviors_total_time and
                                    row["behavior"] not in parameters[cfg.EXCLUDED_BEHAVIORS]):
                                tot_time -= excl_behaviors_total_time[row["subject"]]
                            values.append(round(row["duration"] / tot_time * 100, 1) if tot_time > 0 else "-")
                        else:
                            values.append("-")

                        rows.append(values)

                if mode == "by_category":
                    rows.append(tb_fields)

                    for subject in categories:

                        for category in categories[subject]:
                            values = []
                            values.append(subject)
                            if category == "":
                                values.append("No category")
                            else:
                                values.append(category)

                            values.append(categories[subject][category]["number"])
                            try:
                                values.append(f"{categories[subject][category]['duration']:0.3f}")
                            except Exception:
                                values.append(categories[subject][category]["duration"])

                            rows.append(values)

            data = tablib.Dataset()
            data.title = obsId
            for row in rows:
                data.append(util.complete(row, max([len(r) for r in rows])))

            # check worksheet/workbook title for forbidden char (excel)
            data.title = util.safe_xl_worksheet_title(data.title, extension)
            """
            if "xls" in outputFormat:
                for forbidden_char in EXCEL_FORBIDDEN_CHARACTERS:
                    data.title = data.title.replace(forbidden_char, " ")
            """

            if flagWorkBook:
                """
                for forbidden_char in EXCEL_FORBIDDEN_CHARACTERS:
                    data.title = data.title.replace(forbidden_char, " ")
                if "xls" in outputFormat:
                    if len(data.title) > 31:
                        data.title = data.title[:31]
                """
                workbook.add_sheet(data)

            else:

                fileName = f"{pl.Path(exportDir) / pl.Path(util.safeFileName(obsId))}.{extension}"
                if mem_command != cfg.OVERWRITE_ALL and pl.Path(fileName).is_file():
                    if mem_command == "Skip all":
                        continue
                    mem_command = dialog.MessageDialog(
                        cfg.programName,
                        f"The file {fileName} already exists.",
                        [cfg.OVERWRITE, cfg.OVERWRITE_ALL, "Skip", "Skip all", cfg.CANCEL],
                    )
                    if mem_command == cfg.CANCEL:
                        return
                    if mem_command in ["Skip", "Skip all"]:
                        continue

                if outputFormat in ["tsv", "csv", "html"]:
                    with open(fileName, "wb") as f:
                        f.write(str.encode(data.export(outputFormat)))

                if outputFormat == "od spreadsheet":
                    with open(fileName, "wb") as f:
                        f.write(data.ods)

                if outputFormat == "xlsx spreadsheet":
                    with open(fileName, "wb") as f:
                        f.write(data.xlsx)

                if outputFormat == "xls legacy":
                    """
                    if len(data.title) > 31:
                        data.title = data.title[:31]
                        QMessageBox.warning(
                            None,
                            programName,
                            (f"The worksheet name <b>{obsId}</b> was shortened to <b>{data.title}</b> due to XLS format limitations.\n"
                                "The limit on worksheet name length is 31 characters"),
                            QMessageBox.Ok | QMessageBox.Default, QMessageBox.NoButton
                        )
                    """

                    with open(fileName, "wb") as f:
                        f.write(data.xls)

        if flagWorkBook:
            if "xls" in outputFormat:
                with open(WBfileName, "wb") as f:
                    f.write(workbook.xlsx)
            if "od" in outputFormat:
                with open(WBfileName, "wb") as f:
                    f.write(workbook.ods)
