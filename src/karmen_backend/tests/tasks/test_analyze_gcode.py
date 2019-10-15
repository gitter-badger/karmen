import unittest
import mock
import tempfile

from server.tasks.analyze_gcode import analyze_gcode


class AnalyzeGcodeTest(unittest.TestCase):
    @mock.patch("server.tasks.analyze_gcode.app.logger.error")
    @mock.patch("server.database.gcodes.get_gcode", return_value=None)
    def test_record_not_found(self, mock_gcode_get, mock_logger):
        analyze_gcode(123)
        self.assertTrue(mock_logger.call_count, 1)
        mock_logger.called_with("Gcode does not exist in database")

    @mock.patch("server.tasks.analyze_gcode.app.logger.error")
    @mock.patch(
        "server.database.gcodes.get_gcode",
        return_value={"absolute_path": "/a/karmen-random-file"},
    )
    def test_file_not_found(self, mock_gcode_get, mock_logger):
        analyze_gcode(123)
        self.assertTrue(mock_logger.call_count, 1)
        mock_logger.called_with("Gcode file not found")

    @mock.patch("server.database.gcodes.set_analysis_result")
    @mock.patch(
        "server.database.gcodes.get_gcode",
        return_value={"absolute_path": "/a/karmen-random-file"},
    )
    def test_file_prusaslicer(self, mock_gcode_get, mock_analysis_set):
        config_data = mock.mock_open(
            read_data=b"""
; generated by PrusaSlicer 2.0.0+linux64 on 2019-09-25 at 13:08:24

; 

M73 Q0 S3
M201 X1000 Y1000 Z1000 E5000 ; sets maximum accelerations, mm/sec^2
M203 X200 Y200 Z12 E120 ; sets maximum feedrates, mm/sec
M204 P1250 R1250 T1250 ; sets acceleration (P, T) and retract acceleration (R), mm/sec^2
M205 X8.00 Y8.00 Z0.40 E1.50 ; sets the jerk limits, mm/sec
; filament used [mm] = 94.7
; filament used [cm3] = 0.2
; filament used [g] = 0.3
; filament cost = 0.0
; total filament used [g] = 0.3
; total filament cost = 0.0
; estimated printing time (normal mode) = 3m 13s
; estimated printing time (silent mode) = 3m 14s

M204 S1250
G1 F961
G1 X133.970 Y110.786 E0.05716
G1 X133.926 Y111.001 E0.00673
G1 X133.924 Y111.355 E0.01085

; filament_toolchange_delay = 0
; filament_type = PLA
; filament_unload_time = 0
; filament_unloading_speed = 90
; filament_unloading_speed_start = 100
; first_layer_acceleration = 1000
; first_layer_bed_temperature = 60
; first_layer_extrusion_width = 0.42
; first_layer_speed = 20
; first_layer_temperature = 215
; gcode_comments = 0
; gcode_flavor = marlin
; temperature = 215
; bed_temperature = 60
"""
        )
        with mock.patch("server.tasks.analyze_gcode.open", config_data) as mock_open:
            analyze_gcode(123)
            mock_analysis_set.assert_called_once_with(
                123,
                {
                    "filament": {"length_mm": 94.7, "volume_cm3": 0.2, "type": "PLA"},
                    "temperatures": {
                        "bed": 60.0,
                        "bed_first": 60.0,
                        "tool0": 215.0,
                        "tool0_first": 215.0,
                    },
                    "time": {"estimate_s": 193},
                },
            )

    @mock.patch("server.database.gcodes.set_analysis_result")
    @mock.patch(
        "server.database.gcodes.get_gcode",
        return_value={"absolute_path": "/a/karmen-random-file"},
    )
    def test_file_cura(self, mock_gcode_get, mock_analysis_set):
        config_data = mock.mock_open(
            read_data=b"""
;FLAVOR:Marlin
;TIME:160
;Filament used: 0.203432m
;Layer height: 0.2
;MINX:79.205
;MINY:83.508
;MINZ:0.3
;MAXX:120.793
;MAXY:116.48
;MAXZ:1.5
;Generated with Cura_SteamEngine 4.3.0
M140 S60
M105
M190 S60
M104 S200
M105
M109 S200
M82 ;absolute extrusion mode
G21 ;metric values

G1 X87.175 Y86.572 E0.21548
G1 X87.856 Y86.222 E0.25368
G1 X88.501 Y85.93 E0.28901
G1 X89.169 Y85.664 E0.32488
G1 X89.837 Y85.433 E0.36014
G1 X90.539 Y85.227 E0.39664
G1 X91.224 Y85.06 E0.43182
G1 X91.948 Y84.919 E0.46861

G1 X109.13 Y106.302
;TIME_ELAPSED:160.596768
G1 F1500 E196.9317
M140 S0
M107
M104 S0 ;extruder heater off
M140 S0 ;heated bed heater off (if you have it)
G91 ;relative positioning
G1 E-1 F300  ;retract the filament a bit before lifting the nozzle, to release some of the pressure
G1 Z+0.5 E-5 X-20 Y-20 F9000 ;move Z up a bit and retract filament even more
G28 X0 Y0 ;move X/Y to min endstops, so the head is out of the way
M84 ;steppers off
G90 ;absolute positioning
M82 ;absolute extrusion mode
M104 S0
;End of Gcode
"""
        )
        with mock.patch("server.tasks.analyze_gcode.open", config_data) as mock_open:
            analyze_gcode(123)
            mock_analysis_set.assert_called_once_with(
                123,
                {
                    "filament": {
                        "length_mm": 203.432,
                        "volume_cm3": None,
                        "type": None,
                    },
                    "temperatures": {
                        "bed": None,
                        "bed_first": None,
                        "tool0": None,
                        "tool0_first": None,
                    },
                    "time": {"estimate_s": 160},
                },
            )
