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

import tablib
import logging
import os
import sys
import datetime
import pathlib
from . import dialog
from decimal import Decimal

from . import config as cfg
from . import utilities as util
from . import project_functions
from . import db_functions


def export_events_jwatcher(
    parameters: list, obsId: str, observation: list, ethogram: dict, file_name: str, output_format: str
) -> tuple:
    """
    export events jwatcher .dat format

    Args:
        parameters (dict): subjects, behaviors
        obsId (str): observation id
        observation (dict): observation
        ethogram (dict): ethogram of project
        file_name (str): file name for exporting events
        output_format (str): Not used for compatibility with export_events function

    Returns:
        bool: result: True if OK else False
        str: error message
    """
    for subject in parameters["selected subjects"]:

        # select events for current subject
        events = []
        for event in observation[cfg.EVENTS]:
            if event[cfg.EVENT_SUBJECT_FIELD_IDX] == subject or (
                subject == "No focal subject" and event[cfg.EVENT_SUBJECT_FIELD_IDX] == ""
            ):
                events.append(event)

        if not events:
            continue

        total_length = 0  # in seconds
        if observation[cfg.EVENTS]:
            total_length = (
                observation[cfg.EVENTS][-1][0] - observation[cfg.EVENTS][0][0]
            )  # last event time - first event time

        file_name_subject = str(pathlib.Path(file_name).parent / pathlib.Path(file_name).stem) + "_" + subject + ".dat"

        rows = ["FirstLineOfData"]  # to be completed
        rows.append("#-----------------------------------------------------------")
        rows.append(f"# Name: {pathlib.Path(file_name_subject).name}")
        rows.append("# Format: Focal Data File 1.0")
        rows.append(f"# Updated: {datetime.datetime.now().isoformat()}")
        rows.append("#-----------------------------------------------------------")
        rows.append("")
        rows.append(f"FocalMasterFile={pathlib.Path(file_name_subject).with_suffix('.fmf')}")
        rows.append("")

        rows.append(f"# Observation started: {observation['date']}")
        try:
            start_time = datetime.datetime.strptime(observation["date"], "%Y-%m-%dT%H:%M:%S")
        except ValueError:
            start_time = datetime.datetime(1970, 1, 1, 0, 0)
        start_time_epoch = int((start_time - datetime.datetime(1970, 1, 1, 0, 0)).total_seconds() * 1000)
        rows.append(f"StartTime={start_time_epoch}")

        stop_time = (start_time + datetime.timedelta(seconds=float(total_length))).isoformat()
        stop_time_epoch = int(start_time_epoch + float(total_length) * 1000)

        rows.append(f"# Observation stopped: {stop_time}")
        rows.append(f"StopTime={stop_time_epoch}")

        rows.extend([""] * 3)
        rows.append("#BEGIN DATA")
        rows[0] = f"FirstLineOfData={len(rows) + 1}"

        all_observed_behaviors = []
        mem_number_of_state_events = {}
        for event in events:
            behav_code = event[cfg.EVENT_BEHAVIOR_FIELD_IDX]

            try:
                behavior_key = [
                    ethogram[k][cfg.BEHAVIOR_KEY] for k in ethogram if ethogram[k][cfg.BEHAVIOR_CODE] == behav_code
                ][0]
            except Exception:
                # coded behavior not defined in ethogram
                continue
            if [ethogram[k][cfg.TYPE] for k in ethogram if ethogram[k][cfg.BEHAVIOR_CODE] == behav_code] == [
                cfg.STATE_EVENT
            ]:
                if behav_code in mem_number_of_state_events:
                    mem_number_of_state_events[behav_code] += 1
                else:
                    mem_number_of_state_events[behav_code] = 1
                # skip the STOP event in case of STATE
                if mem_number_of_state_events[behav_code] % 2 == 0:
                    continue

            rows.append(f"{int(event[cfg.EVENT_TIME_FIELD_IDX] * 1000)}, {behavior_key}")
            if (event[cfg.EVENT_BEHAVIOR_FIELD_IDX], behavior_key) not in all_observed_behaviors:
                all_observed_behaviors.append((event[cfg.EVENT_BEHAVIOR_FIELD_IDX], behavior_key))

        rows.append(f"{int(events[-1][0] * 1000)}, EOF\n")

        try:
            with open(file_name_subject, "w") as f_out:
                f_out.write("\n".join(rows))
        except Exception:
            return False, f"File DAT not created for subject {subject}: {sys.exc_info()[1]}"

        # create fmf file
        fmf_file_path = pathlib.Path(file_name_subject).with_suffix(".fmf")
        fmf_creation_answer = ""
        if fmf_file_path.exists():
            fmf_creation_answer = dialog.MessageDialog(
                cfg.programName,
                (f"The {fmf_file_path} file already exists.<br>" "What do you want to do?"),
                [cfg.OVERWRITE, "Skip file creation", cfg.CANCEL],
            )

            if fmf_creation_answer == cfg.CANCEL:
                return True, ""

        rows = []
        rows.append("#-----------------------------------------------------------")
        rows.append(f"# Name: {pathlib.Path(file_name_subject).with_suffix('.fmf').name}")
        rows.append("# Format: Focal Master File 1.0")
        rows.append(f"# Updated: {datetime.datetime.now().isoformat()}")
        rows.append("#-----------------------------------------------------------")
        for (behav, key) in all_observed_behaviors:
            rows.append(f"Behaviour.name.{key}={behav}")
            behav_description = [
                ethogram[k][cfg.DESCRIPTION] for k in ethogram if ethogram[k][cfg.BEHAVIOR_CODE] == behav
            ][0]
            rows.append(f"Behaviour.description.{key}={behav_description}")

        rows.append(f"DurationMilliseconds={int(float(total_length) * 1000)}")
        rows.append("CountUp=false")
        rows.append("Question.1=")
        rows.append("Question.2=")
        rows.append("Question.3=")
        rows.append("Question.4=")
        rows.append("Question.5=")
        rows.append("Question.6=")
        rows.append("Notes=")
        rows.append("Supplementary=\n")

        if fmf_creation_answer == cfg.OVERWRITE or fmf_creation_answer == "":
            try:
                with open(fmf_file_path, "w") as f_out:
                    f_out.write("\n".join(rows))
            except Exception:
                return False, f"File FMF not created: {sys.exc_info()[1]}"

        # create FAF file
        faf_file_path = pathlib.Path(file_name_subject).with_suffix(".faf")
        faf_creation_answer = ""
        if faf_file_path.exists():
            faf_creation_answer = dialog.MessageDialog(
                cfg.programName,
                (f"The {faf_file_path} file already exists.<br>" "What do you want to do?"),
                [cfg.OVERWRITE, "Skip file creation", cfg.CANCEL],
            )
            if faf_creation_answer == cfg.CANCEL:
                return True, ""

        rows = []
        rows.append("#-----------------------------------------------------------")
        rows.append("# Name: {}".format(pathlib.Path(file_name_subject).with_suffix(".faf").name))
        rows.append("# Format: Focal Analysis Master File 1.0")
        rows.append("# Updated: {}".format(datetime.datetime.now().isoformat()))
        rows.append("#-----------------------------------------------------------")
        rows.append("FocalMasterFile={}".format(str(pathlib.Path(file_name_subject).with_suffix(".fmf"))))
        rows.append("")
        rows.append("TimeBinDuration=0.0")
        rows.append("EndWithLastCompleteBin=true")
        rows.append("")
        rows.append("ScoreFromBeginning=true")
        rows.append("ScoreFromBehavior=false")
        rows.append("ScoreFromFirstBehavior=false")
        rows.append("ScoreFromOffset=false")
        rows.append("")
        rows.append("Offset=0.0")
        rows.append("BehaviorToScoreFrom=")
        rows.append("")
        rows.append("OutOfSightCode=")
        rows.append("")
        rows.append("Report.StateNaturalInterval.Occurrence=false")
        rows.append("Report.StateNaturalInterval.TotalTime=false")
        rows.append("Report.StateNaturalInterval.Average=false")
        rows.append("Report.StateNaturalInterval.StandardDeviation=false")
        rows.append("Report.StateNaturalInterval.ProportionOfTime=false")
        rows.append("Report.StateNaturalInterval.ProportionOfTimeInSight=false")
        rows.append("Report.StateNaturalInterval.ConditionalProportionOfTime=false")
        rows.append("")
        rows.append("Report.StateNaturalDuration.Occurrence=false")
        rows.append("Report.StateNaturalDuration.TotalTime=false")
        rows.append("Report.StateNaturalDuration.Average=false")
        rows.append("Report.StateNaturalDuration.StandardDeviation=false")
        rows.append("Report.StateNaturalDuration.ProportionOfTime=false")
        rows.append("Report.StateNaturalDuration.ProportionOfTimeInSight=false")
        rows.append("Report.StateNaturalDuration.ConditionalProportionOfTime=false")
        rows.append("")
        rows.append("Report.StateAllInterval.Occurrence=false")
        rows.append("Report.StateAllInterval.TotalTime=false")
        rows.append("Report.StateAllInterval.Average=false")
        rows.append("Report.StateAllInterval.StandardDeviation=false")
        rows.append("Report.StateAllInterval.ProportionOfTime=false")
        rows.append("Report.StateAllInterval.ProportionOfTimeInSight=false")
        rows.append("Report.StateAllInterval.ConditionalProportionOfTime=false")
        rows.append("")
        rows.append("Report.StateAllDuration.Occurrence=true")
        rows.append("Report.StateAllDuration.TotalTime=true")
        rows.append("Report.StateAllDuration.Average=true")
        rows.append("Report.StateAllDuration.StandardDeviation=false")
        rows.append("Report.StateAllDuration.ProportionOfTime=false")
        rows.append("Report.StateAllDuration.ProportionOfTimeInSight=true")
        rows.append("Report.StateAllDuration.ConditionalProportionOfTime=false")
        rows.append("")
        rows.append("Report.EventNaturalInterval.EventCount=false")
        rows.append("Report.EventNaturalInterval.Occurrence=false")
        rows.append("Report.EventNaturalInterval.Average=false")
        rows.append("Report.EventNaturalInterval.StandardDeviation=false")
        rows.append("Report.EventNaturalInterval.ConditionalNatEventCount=false")
        rows.append("Report.EventNaturalInterval.ConditionalNatRate=false")
        rows.append("Report.EventNaturalInterval.ConditionalNatIntervalOccurance=false")
        rows.append("Report.EventNaturalInterval.ConditionalNatIntervalAverage=false")
        rows.append("Report.EventNaturalInterval.ConditionalNatIntervalStandardDeviation=false")
        rows.append("Report.EventNaturalInterval.ConditionalAllEventCount=false")
        rows.append("Report.EventNaturalInterval.ConditionalAllRate=false")
        rows.append("Report.EventNaturalInterval.ConditionalAllIntervalOccurance=false")
        rows.append("Report.EventNaturalInterval.ConditionalAllIntervalAverage=false")
        rows.append("Report.EventNaturalInterval.ConditionalAllIntervalStandardDeviation=false")
        rows.append("")
        rows.append("AllCodesMutuallyExclusive=true")
        rows.append("")

        for (behav, key) in all_observed_behaviors:
            rows.append(f"Behavior.isModified.{key}=false")
            rows.append(f"Behavior.isSubtracted.{key}=false")
            rows.append(f"Behavior.isIgnored.{key}=false")
            rows.append(f"Behavior.isEventAnalyzed.{key}=false")
            rows.append(f"Behavior.switchesOff.{key}=")
            rows.append("")

        if faf_creation_answer == "" or faf_creation_answer == cfg.OVERWRITE:
            try:
                with open(pathlib.Path(file_name_subject).with_suffix(".faf"), "w") as f_out:
                    f_out.write("\n".join(rows))
            except Exception:
                return False, f"File FAF not created: {sys.exc_info()[1]}"

    return True, ""


def export_events(
    parameters, obsId: str, observation: dict, ethogram: dict, file_name: str, output_format: str
) -> tuple:
    """
    export events

    Args:
        parameters (dict): subjects, behaviors
        obsId (str): observation id
        observation (dict): observation
        ethogram (dict): ethogram of project
        file_name (str): file name for exporting events
        output_format (str): output for exporting events

    Returns:
        bool: result: True if OK else False
        str: error message
    """

    total_length = f"{project_functions.observation_total_length(observation):.3f}"

    eventsWithStatus = project_functions.events_start_stop(ethogram, observation[cfg.EVENTS])

    # check max number of modifiers
    max_modifiers = 0
    for event in eventsWithStatus:
        if event[cfg.EVENT_MODIFIER_FIELD_IDX]:
            max_modifiers = max(max_modifiers, len(event[cfg.EVENT_MODIFIER_FIELD_IDX].split("|")))

    # media file number
    mediaNb = 0
    if observation[cfg.TYPE] == cfg.MEDIA:
        for player in observation[cfg.FILE]:
            mediaNb += len(observation[cfg.FILE][player])

    rows = []

    # observation id
    rows.append(["Observation id", obsId])
    rows.append([""])

    # media file name
    if observation[cfg.TYPE] == cfg.MEDIA:
        rows.append(["Media file(s)"])
    elif observation[cfg.TYPE] == cfg.LIVE:
        rows.append(["Live observation"])
    elif observation[cfg.TYPE] == cfg.IMAGES:
        rows.append(["From directories of images"])
    else:
        rows.append([""])
    rows.append([""])

    if observation[cfg.TYPE] == cfg.MEDIA:
        for player in sorted(list(observation[cfg.FILE].keys())):
            for media in observation[cfg.FILE][player]:
                rows.append([f"Player #{player}", media])

    if observation[cfg.TYPE] == cfg.IMAGES:
        for dir in observation[cfg.DIRECTORIES_LIST]:
            rows.append([f"Directory", dir])

    rows.append([""])

    # date
    rows.append(["Observation date", observation.get("date", "").replace("T", " ")])
    rows.append([""])

    # description
    rows.append(["Description", util.eol2space(observation.get("description", ""))])
    rows.append([""])

    # time offset
    rows.append(["Time offset (s)", observation.get(cfg.TIME_OFFSET, 0)])
    rows.append([""])

    # independent variables
    if cfg.INDEPENDENT_VARIABLES in observation:
        rows.extend([["independent variables"], ["variable", "value"]])

        for variable in observation[cfg.INDEPENDENT_VARIABLES]:
            rows.append([variable, observation[cfg.INDEPENDENT_VARIABLES][variable]])

    rows.append([""])

    # write table header
    col = 0
    header = ["Time"]
    if observation[cfg.TYPE] == cfg.MEDIA:
        header.extend(["Media file path", "Total length", "FPS"])
    if observation[cfg.TYPE] == cfg.IMAGES:
        header.extend(
            [
                "Image file path",
                "Image index",
            ]
        )
    if observation[cfg.TYPE] == cfg.LIVE:
        header.extend(
            [
                "Total length",
            ]
        )

    header.extend(["Subject", "Behavior", "Behavioral category"])

    behavioral_category = project_functions.behavior_category(ethogram)

    for x in range(1, max_modifiers + 1):
        header.append(f"Modifier {x}")
    header.extend(["Comment", "Status"])

    rows.append(header)

    duration1 = []  # in seconds
    if observation[cfg.TYPE] == cfg.MEDIA:
        try:
            for mediaFile in observation[cfg.FILE][cfg.PLAYER1]:
                duration1.append(observation[cfg.MEDIA_INFO][cfg.LENGTH][mediaFile])
        except KeyError:
            pass

    for event in eventsWithStatus:
        if (
            (event[cfg.EVENT_SUBJECT_FIELD_IDX] in parameters[cfg.SELECTED_SUBJECTS])
            or (event[cfg.EVENT_SUBJECT_FIELD_IDX] == "" and cfg.NO_FOCAL_SUBJECT in parameters[cfg.SELECTED_SUBJECTS])
        ) and (event[cfg.EVENT_BEHAVIOR_FIELD_IDX] in parameters[cfg.SELECTED_BEHAVIORS]):

            fields = []
            fields.append(util.intfloatstr(str(event[cfg.EVENT_TIME_FIELD_IDX])))

            if observation[cfg.TYPE] == cfg.MEDIA:

                time_ = event[cfg.EVENT_TIME_FIELD_IDX] - observation[cfg.TIME_OFFSET]
                if time_ < 0:
                    time_ = 0

                if duration1:
                    mediaFileIdx = [idx1 for idx1, x in enumerate(duration1) if time_ >= sum(duration1[0:idx1])][-1]
                    fields.append(observation[cfg.FILE][cfg.PLAYER1][mediaFileIdx])
                    fields.append(total_length)
                    # FPS
                    try:
                        fields.append(
                            observation[cfg.MEDIA_INFO][cfg.FPS][observation[cfg.FILE][cfg.PLAYER1][mediaFileIdx]]
                        )  # fps
                    except KeyError:
                        fields.append(cfg.NA)
                else:
                    fields.append(cfg.NA)  # media file
                    fields.append(cfg.NA)  # FPS

            if observation[cfg.TYPE] == cfg.LIVE:
                fields.append(total_length)  # total length

            if observation[cfg.TYPE] == cfg.IMAGES:
                print(cfg.PJ_EVENTS_FIELDS)
                fields.append(event[cfg.PJ_OBS_FIELDS[cfg.IMAGES][cfg.IMAGE_PATH]])  # image file path
                fields.append(event[cfg.PJ_OBS_FIELDS[cfg.IMAGES][cfg.IMAGE_INDEX]])  # image file index

            fields.append(event[cfg.PJ_OBS_FIELDS[observation[cfg.TYPE]][cfg.SUBJECT]])
            fields.append(event[cfg.PJ_OBS_FIELDS[observation[cfg.TYPE]][cfg.BEHAVIOR_CODE]])

            # behavioral category

            try:
                behav_category = behavioral_category[event[cfg.PJ_OBS_FIELDS[observation[cfg.TYPE]][cfg.BEHAVIOR_CODE]]]
            except Exception:
                behav_category = ""
            fields.append(behav_category)

            # modifiers
            if max_modifiers:
                modifiers = event[cfg.PJ_OBS_FIELDS[observation[cfg.TYPE]][cfg.MODIFIER]].split("|")
                while len(modifiers) < max_modifiers:
                    modifiers.append("")

                for m in modifiers:
                    fields.append(m)

            # comment
            fields.append(event[cfg.PJ_OBS_FIELDS[observation[cfg.TYPE]][cfg.COMMENT]].replace(os.linesep, " "))
            # status
            fields.append(event[-1])

            rows.append(fields)

    maxLen = max([len(r) for r in rows])
    data = tablib.Dataset()

    data.title = util.safe_xl_worksheet_title(obsId, output_format)

    for row in rows:
        data.append(util.complete(row, maxLen))

    r, msg = dataset_write(data, file_name, output_format)

    return r, msg


def dataset_write(dataset, file_name, output_format):
    """
    write a tablib dataset to file in specified format

    Args:
        dataset (tablib.dataset): dataset to write
        file_name (str): file name
        output_format (str): format of output

    Returns:
        bool: result. True if OK else False
        str: error message
    """

    logging.debug("function: dataset_write")

    try:
        if output_format == "tsv":
            with open(file_name, "wb") as f:
                f.write(str.encode(dataset.tsv))
            return True, ""
        if output_format == "csv":
            with open(file_name, "wb") as f:
                f.write(str.encode(dataset.csv))
            return True, ""
        if output_format == "ods":
            with open(file_name, "wb") as f:
                f.write(dataset.ods)
            return True, ""

        dataset.title = util.safe_xl_worksheet_title(dataset.title, output_format)
        """
        if output_format in ["xls", "xlsx"]:
            # check worksheet title
            for forbidden_char in EXCEL_FORBIDDEN_CHARACTERS:
                dataset.title = dataset.title.replace(forbidden_char, " ")
        """
        if output_format == "xlsx":
            with open(file_name, "wb") as f:
                f.write(dataset.xlsx)
            return True, ""

        if output_format == "xls":
            if len(dataset.title) > 31:
                dataset.title = dataset.title[:31]
            with open(file_name, "wb") as f:
                f.write(dataset.xls)
            return True, ""

        if output_format == "html":
            with open(file_name, "wb") as f:
                f.write(str.encode(dataset.html))
            return True, ""

        return False, f"Format {output_format} not found"

    except Exception:
        return False, str(sys.exc_info()[1])


def export_aggregated_events(pj: dict, parameters: dict, obsId: str):
    """
    export aggregated events

    Args:
        pj (dict): BORIS project
        parameters (dict): subjects, behaviors
        obsId (str): observation id

    Returns:
        tablib.Dataset:

    """
    logging.debug(f"function: export aggregated events {parameters} {obsId}")

    interval = parameters["time"]
    start_time = parameters[cfg.START_TIME]
    end_time = parameters[cfg.END_TIME]

    data = tablib.Dataset()
    observation = pj[cfg.OBSERVATIONS][obsId]

    # obs description
    obs_description = observation[cfg.DESCRIPTION]

    duration1 = []  # in seconds
    if observation[cfg.TYPE] == cfg.MEDIA:
        try:
            for mediaFile in observation[cfg.FILE][cfg.PLAYER1]:
                if cfg.MEDIA_INFO in observation:
                    duration1.append(observation[cfg.MEDIA_INFO][cfg.LENGTH][mediaFile])
        except Exception:
            duration1 = []

    obs_length = project_functions.observation_total_length(pj[cfg.OBSERVATIONS][obsId])
    if obs_length == Decimal(-1):  # media length not available
        interval = cfg.TIME_EVENTS

    print(f"{interval=}")
    logging.debug(f"obs_length: {obs_length}")

    _, _, connector = db_functions.load_aggregated_events_in_db(
        pj, parameters[cfg.SELECTED_SUBJECTS], [obsId], parameters[cfg.SELECTED_BEHAVIORS]
    )
    if connector is None:
        logging.critical(f"error when loading aggregated events in DB")
        return data

    # time
    cursor = connector.cursor()

    if interval == cfg.TIME_FULL_OBS:
        min_time = float(0)
        max_time = float(obs_length)

    if interval == cfg.TIME_EVENTS:
        try:
            min_time = float(pj[cfg.OBSERVATIONS][obsId][cfg.EVENTS][0][0])
        except Exception:
            min_time = float(0)
        try:
            max_time = float(pj[cfg.OBSERVATIONS][obsId][cfg.EVENTS][-1][0])
        except Exception:
            max_time = float(obs_length)

    if interval == cfg.TIME_ARBITRARY_INTERVAL:
        min_time = float(start_time)
        max_time = float(end_time)

    # adapt start and stop to the selected time interval
    cursor.execute(
        "UPDATE aggregated_events SET start = ? WHERE observation = ? AND start < ? AND stop BETWEEN ? AND ?",
        (
            min_time,
            obsId,
            min_time,
            min_time,
            max_time,
        ),
    )
    cursor.execute(
        "UPDATE aggregated_events SET stop = ? WHERE observation = ? AND stop > ? AND start BETWEEN ? AND ?",
        (
            max_time,
            obsId,
            max_time,
            min_time,
            max_time,
        ),
    )

    cursor.execute(
        "UPDATE aggregated_events SET start = ?, stop = ? WHERE observation = ? AND start < ? AND stop > ?",
        (
            min_time,
            max_time,
            obsId,
            min_time,
            max_time,
        ),
    )

    cursor.execute(
        "DELETE FROM aggregated_events WHERE observation = ? AND (start < ? AND stop < ?) OR (start > ? AND stop > ?)",
        (
            obsId,
            min_time,
            min_time,
            max_time,
            max_time,
        ),
    )

    behavioral_category = project_functions.behavior_category(pj[cfg.ETHOGRAM])

    for subject in parameters[cfg.SELECTED_SUBJECTS]:

        for behavior in parameters[cfg.SELECTED_BEHAVIORS]:

            cursor.execute(
                "SELECT distinct modifiers FROM aggregated_events where subject=? AND behavior=? order by modifiers",
                (
                    subject,
                    behavior,
                ),
            )

            rows_distinct_modifiers = list(x[0] for x in cursor.fetchall())

            for distinct_modifiers in rows_distinct_modifiers:

                cursor.execute(
                    (
                        "SELECT start, stop, type, modifiers, comment, comment_stop FROM aggregated_events "
                        "WHERE subject = ? AND behavior = ? AND modifiers = ? ORDER by start"
                    ),
                    (subject, behavior, distinct_modifiers),
                )
                rows = list(cursor.fetchall())

                for row in rows:

                    if observation[cfg.TYPE] == cfg.MEDIA:
                        if duration1:
                            mediaFileIdx = [
                                idx1 for idx1, _ in enumerate(duration1) if row["start"] >= sum(duration1[0:idx1])
                            ][-1]
                            mediaFileString = observation[cfg.FILE][cfg.PLAYER1][mediaFileIdx]
                            try:
                                fpsString = observation[cfg.MEDIA_INFO]["fps"][
                                    observation[cfg.FILE][cfg.PLAYER1][mediaFileIdx]
                                ]
                            except Exception:
                                fpsString = cfg.NA
                        else:
                            try:
                                if len(observation[cfg.FILE][cfg.PLAYER1]) == 1:
                                    mediaFileString = observation[cfg.FILE][cfg.PLAYER1][0]
                                else:
                                    mediaFileString = cfg.NA
                            except Exception:
                                mediaFileString = cfg.NA
                            fpsString = cfg.NA

                    if observation[cfg.TYPE] == cfg.LIVE:
                        mediaFileString = "LIVE"
                        fpsString = cfg.NA

                    if observation[cfg.TYPE] == cfg.IMAGES:
                        mediaFileString = "IMAGES"
                        fpsString = cfg.NA

                    if row["type"] == cfg.POINT:

                        row_data = []
                        row_data.extend(
                            [
                                obsId,
                                observation["date"].replace("T", " "),
                                obs_description,
                                mediaFileString,
                                f"{obs_length:.3f}" if obs_length != Decimal("-1") else cfg.NA,
                                fpsString,
                            ]
                        )

                        # independent variables
                        if cfg.INDEPENDENT_VARIABLES in pj:
                            for idx_var in util.sorted_keys(pj[cfg.INDEPENDENT_VARIABLES]):
                                if (
                                    pj[cfg.INDEPENDENT_VARIABLES][idx_var]["label"]
                                    in observation[cfg.INDEPENDENT_VARIABLES]
                                ):
                                    row_data.append(
                                        observation[cfg.INDEPENDENT_VARIABLES][
                                            pj[cfg.INDEPENDENT_VARIABLES][idx_var]["label"]
                                        ]
                                    )
                                else:
                                    row_data.append("")

                        row_data.extend(
                            [
                                subject,
                                behavior,
                                behavioral_category[behavior],
                                row["modifiers"],
                                cfg.POINT,
                                f"{row['start']:.3f}",  # start
                                f"{row['stop']:.3f}",  # stop
                                cfg.NA,  # duration
                                row["comment"],
                                "",
                            ]
                        )
                        data.append(row_data)

                    if row["type"] == cfg.STATE:
                        row_data = []
                        row_data.extend(
                            [
                                obsId,
                                observation["date"].replace("T", " "),
                                obs_description,
                                mediaFileString,
                                f"{obs_length:.3f}" if obs_length != Decimal("-1") else "NA",
                                fpsString,
                            ]
                        )

                        # independent variables
                        if cfg.INDEPENDENT_VARIABLES in pj:
                            for idx_var in util.sorted_keys(pj[cfg.INDEPENDENT_VARIABLES]):
                                if (
                                    pj[cfg.INDEPENDENT_VARIABLES][idx_var]["label"]
                                    in observation[cfg.INDEPENDENT_VARIABLES]
                                ):
                                    row_data.append(
                                        observation[cfg.INDEPENDENT_VARIABLES][
                                            pj[cfg.INDEPENDENT_VARIABLES][idx_var]["label"]
                                        ]
                                    )
                                else:
                                    row_data.append("")

                        row_data.extend(
                            [
                                subject,
                                behavior,
                                behavioral_category[behavior],
                                row["modifiers"],
                                cfg.STATE,
                                f"{row['start']:.3f}",
                                f"{row['stop']:.3f}",
                                f"{row['stop'] - row['start']:.3f}",
                                row["comment"],
                                row["comment_stop"],
                            ]
                        )
                        data.append(row_data)

    return data


def events_to_behavioral_sequences(pj, obs_id: str, subj: str, parameters: dict, behav_seq_separator: str) -> str:
    """
    return the behavioral sequence (behavioral string) for subject in obs_id

    Args:
        pj (dict): project
        obs_id (str): observation id
        subj (str): subject
        parameters (dict): parameters
        behav_seq_separator (str): separator of behviors in behavioral sequences

    Returns:
        str: behavioral string for selected subject in selected observation
    """

    out = ""
    current_states = []
    events_with_status = project_functions.events_start_stop(pj[cfg.ETHOGRAM], pj[cfg.OBSERVATIONS][obs_id][cfg.EVENTS])

    for event in events_with_status:
        # check if event in selected behaviors
        if event[cfg.EVENT_BEHAVIOR_FIELD_IDX] not in parameters[cfg.SELECTED_BEHAVIORS]:
            continue

        if event[cfg.EVENT_SUBJECT_FIELD_IDX] == subj or (
            subj == cfg.NO_FOCAL_SUBJECT and event[cfg.EVENT_SUBJECT_FIELD_IDX] == ""
        ):

            if event[cfg.EVENT_STATUS_FIELD_IDX] == cfg.POINT:
                if current_states:
                    out += "+".join(current_states) + "+" + event[cfg.EVENT_BEHAVIOR_FIELD_IDX]
                else:
                    out += event[cfg.EVENT_BEHAVIOR_FIELD_IDX]

                if parameters[cfg.INCLUDE_MODIFIERS]:
                    out += "&" + event[cfg.EVENT_MODIFIER_FIELD_IDX].replace("|", "+")

                out += behav_seq_separator

            if event[cfg.EVENT_STATUS_FIELD_IDX] == cfg.START:
                if parameters[cfg.INCLUDE_MODIFIERS]:
                    current_states.append(
                        (
                            f"{event[cfg.EVENT_BEHAVIOR_FIELD_IDX]}"
                            f"{'&' if event[cfg.EVENT_MODIFIER_FIELD_IDX] else ''}"
                            f"{event[cfg.EVENT_MODIFIER_FIELD_IDX].replace('|', ';')}"
                        )
                    )
                else:
                    current_states.append(event[cfg.EVENT_BEHAVIOR_FIELD_IDX])

                out += "+".join(sorted(current_states))

                out += behav_seq_separator

            if event[cfg.EVENT_STATUS_FIELD_IDX] == cfg.STOP:

                if parameters[cfg.INCLUDE_MODIFIERS]:
                    behav_modif = (
                        f"{event[cfg.EVENT_BEHAVIOR_FIELD_IDX]}"
                        f"{'&' if event[cfg.EVENT_MODIFIER_FIELD_IDX] else ''}"
                        f"{event[cfg.EVENT_MODIFIER_FIELD_IDX].replace('|', ';')}"
                    )
                else:
                    behav_modif = event[cfg.EVENT_BEHAVIOR_FIELD_IDX]
                if behav_modif in current_states:
                    current_states.remove(behav_modif)

                if current_states:
                    out += "+".join(sorted(current_states))

                    out += behav_seq_separator

    # remove last separator (if separator not empty)
    if behav_seq_separator:
        out = out[0 : -len(behav_seq_separator)]

    return out


def events_to_behavioral_sequences_all_subj(
    pj, obs_id: str, subjects_list: list, parameters: dict, behav_seq_separator: str
) -> str:
    """
    return the behavioral sequences for all selected subjects in obs_id

    Args:
        pj (dict): project
        obs_id (str): observation id
        subjects_list (list): list of subjects
        parameters (dict): parameters
        behav_seq_separator (str): separator of behviors in behavioral sequences

    Returns:
        str: behavioral sequences for all selected subjects in selected observation
    """

    out = ""
    current_states = {i: [] for i in subjects_list}
    events_with_status = project_functions.events_start_stop(pj[cfg.ETHOGRAM], pj[cfg.OBSERVATIONS][obs_id][cfg.EVENTS])

    for event in events_with_status:
        # check if event in selected behaviors
        if event[cfg.EVENT_BEHAVIOR_FIELD_IDX] not in parameters[cfg.SELECTED_BEHAVIORS]:
            continue

        if (event[cfg.EVENT_SUBJECT_FIELD_IDX] in subjects_list) or (
            event[cfg.EVENT_SUBJECT_FIELD_IDX] == "" and cfg.NO_FOCAL_SUBJECT in subjects_list
        ):

            subject = event[cfg.EVENT_SUBJECT_FIELD_IDX] if event[cfg.EVENT_SUBJECT_FIELD_IDX] else cfg.NO_FOCAL_SUBJECT

            if event[-1] == cfg.POINT:
                if current_states[subject]:
                    out += (
                        f"[{subject}]" + "+".join(current_states[subject]) + "+" + event[cfg.EVENT_BEHAVIOR_FIELD_IDX]
                    )
                else:
                    out += f"[{subject}]" + event[cfg.EVENT_BEHAVIOR_FIELD_IDX]

                if parameters[cfg.INCLUDE_MODIFIERS]:
                    out += "&" + event[cfg.EVENT_MODIFIER_FIELD_IDX].replace("|", "+")

                out += behav_seq_separator

            if event[-1] == cfg.START:
                if parameters[cfg.INCLUDE_MODIFIERS]:
                    current_states[subject].append(
                        (
                            f"{event[cfg.EVENT_BEHAVIOR_FIELD_IDX]}"
                            f"{'&' if event[cfg.EVENT_MODIFIER_FIELD_IDX] else ''}"
                            f"{event[cfg.EVENT_MODIFIER_FIELD_IDX].replace('|', ';')}"
                        )
                    )
                else:
                    current_states[subject].append(event[cfg.EVENT_BEHAVIOR_FIELD_IDX])

                out += f"[{subject}]" + "+".join(sorted(current_states[subject]))

                out += behav_seq_separator

            if event[-1] == cfg.STOP:

                if parameters[cfg.INCLUDE_MODIFIERS]:
                    behav_modif = (
                        f"{event[cfg.EVENT_BEHAVIOR_FIELD_IDX]}"
                        f"{'&' if event[cfg.EVENT_MODIFIER_FIELD_IDX] else ''}"
                        f"{event[cfg.EVENT_MODIFIER_FIELD_IDX].replace('|', ';')}"
                    )
                else:
                    behav_modif = event[cfg.EVENT_BEHAVIOR_FIELD_IDX]
                if behav_modif in current_states[subject]:
                    current_states[subject].remove(behav_modif)

                if current_states[subject]:
                    out += f"[{subject}]" + "+".join(sorted(current_states[subject]))

                    out += behav_seq_separator

    # remove last separator (if separator not empty)
    if behav_seq_separator:
        out = out[0 : -len(behav_seq_separator)]

    return out


def events_to_timed_behavioral_sequences(
    pj: dict, obs_id: str, subject: str, parameters: dict, precision: float, behav_seq_separator: str
) -> str:
    """
    return the behavioral string for subject in obsId

    Args:
        pj (dict): project
        obs_id (str): observation id
        subj (str): subject
        parameters (dict): parameters
        precision (float): time value for scan sample
        behav_seq_separator (str): separator of behviors in behavioral sequences

    Returns:
        str: behavioral string for selected subject in selected observation
    """

    out = ""
    current_states = []
    # events_with_status = project_functions.events_start_stop(pj[ETHOGRAM], pj[cfg.OBSERVATIONS][obs_id][cfg.EVENTS])

    state_behaviors_codes = util.state_behavior_codes(pj[cfg.ETHOGRAM])
    delta = Decimal(str(round(precision, 3)))
    out = ""
    t = Decimal("0.000")

    current = []
    while t < pj[cfg.OBSERVATIONS][obs_id][cfg.EVENTS][-1][0]:
        """
        if out:
            out += behav_seq_separator
        """
        csbs = util.get_current_states_modifiers_by_subject(
            state_behaviors_codes,
            pj[cfg.OBSERVATIONS][obs_id][cfg.EVENTS],
            {"": {"name": subject}},
            t,
            include_modifiers=False,
        )[""]
        if csbs:
            if current:
                if csbs == current[-1]:
                    current.append("+".join(csbs))
                else:
                    out.append(current)
                    current = [csbs]
            else:
                current = [csbs]

        t += delta

    return out


def observation_to_behavioral_sequences(
    pj, selected_observations, parameters, behaviors_separator, separated_subjects, timed, file_name
):

    try:
        with open(file_name, "w", encoding="utf-8") as out_file:
            for obs_id in selected_observations:
                # observation id
                out_file.write("\n" + f"# observation id: {obs_id}" + "\n")
                # observation description
                descr = pj[cfg.OBSERVATIONS][obs_id]["description"]
                if "\r\n" in descr:
                    descr = descr.replace("\r\n", "\n# ")
                elif "\r" in descr:
                    descr = descr.replace("\r", "\n# ")
                out_file.write(f"# observation description: {descr}\n\n")
                # media file name
                if pj[cfg.OBSERVATIONS][obs_id][cfg.TYPE] in [cfg.MEDIA]:
                    out_file.write(
                        f"# Media file name: {', '.join([os.path.basename(x) for x in pj[cfg.OBSERVATIONS][obs_id][cfg.FILE][cfg.PLAYER1]])}\n\n"
                    )
                if pj[cfg.OBSERVATIONS][obs_id][cfg.TYPE] in [cfg.LIVE]:
                    out_file.write(f"# Live observation{os.linesep}{os.linesep}")

                # independent variables
                if cfg.INDEPENDENT_VARIABLES in pj[cfg.OBSERVATIONS][obs_id]:
                    out_file.write("# Independent variables\n")

                    for variable in pj[cfg.OBSERVATIONS][obs_id][cfg.INDEPENDENT_VARIABLES]:
                        out_file.write(
                            f"# {variable}: {pj[cfg.OBSERVATIONS][obs_id][cfg.INDEPENDENT_VARIABLES][variable]}\n"
                        )
                out_file.write("\n")

                # one sequence for all subjects
                if not separated_subjects:
                    out = events_to_behavioral_sequences_all_subj(
                        pj, obs_id, parameters[cfg.SELECTED_SUBJECTS], parameters, behaviors_separator
                    )
                    if out:
                        out_file.write(out + "\n")

                # one sequence by subject
                if separated_subjects:
                    # selected subjects
                    for subject in parameters[cfg.SELECTED_SUBJECTS]:
                        out_file.write(f"\n# {subject if subject else cfg.NO_FOCAL_SUBJECT}:\n")

                        if not timed:
                            out = events_to_behavioral_sequences(pj, obs_id, subject, parameters, behaviors_separator)
                        if timed:
                            out = events_to_timed_behavioral_sequences(
                                pj, obs_id, subject, parameters, 0.001, behaviors_separator
                            )

                        if out:
                            out_file.write(out + "\n")

            return True, ""

    except Exception:
        error_type, error_file_name, error_lineno = util.error_info(sys.exc_info())
        return False, f"{error_type} {error_file_name} {error_lineno}"
