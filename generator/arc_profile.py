"""ARC (Archery) real-life profile for SYOG2026.

Derived from the real AWAARC1 initial-download feed (2025-10-17) and the
SYOG2026 Common Codes v1.9.1: 9 sessions, 83 scheduled units (33 M + 33 W
individual + 17 mixed team), 32M+32W athletes across 47 NOCs, 17 mixed teams.
Venue/Location use the Common Codes members SAW / AR1 (the real feed used
"AWA", which is not in Common Codes v1.9.1).
"""
from __future__ import annotations

VENUE = "SAW"
VENUE_NAME = "Abdoulaye Wade Stadium"
LOCATION = "AR1"
LOCATION_NAME = "Abdoulaye Wade Stadium - Field"

# 17 NOCs entering one man + one woman (they also form the mixed teams),
# 15 men-only NOCs, 15 women-only NOCs -> 32 M + 32 W athletes.
# FRG and URS were in this list; both are historical NOCs (CC@NOC
# Participation "H") and produced a "Federal Republic of Germany" team. GER
# and KAZ take their places, keeping 17 dual NOCs.
DUAL_NOCS = ["ASA","BAH","BDI","CRC","CZE","EGY","GER","GHA","ITA","JOR","KAZ","KOR","LAO","PLE","PUR","SWE","USA"]
MEN_NOCS = ["BAR","BEL","CAM","COD","CRO","ETH","GUM","INA","ISL","LCA","MOZ","NCA","NOR","OMA","TKM"]
WOMEN_NOCS = ["ALB","AND","AZE","BAN","BEN","CHI","CIV","COL","HUN","IRL","ISV","KGZ","KSA","SEN","SOM"]

# (code, type, start, end, name)
SESSIONS = [
    ('ARC01', 'MOR', '2026-11-07T09:30:00+00:00', '2026-11-07T12:30:00+00:00', 'Session 1'),
    ('ARC02', 'MOR', '2026-11-08T09:30:00+00:00', '2026-11-08T12:34:00+00:00', 'Session 2'),
    ('ARC03', 'AFT', '2026-11-08T14:00:00+00:00', '2026-11-08T17:04:00+00:00', 'Session 3'),
    ('ARC04', 'AFT', '2026-11-09T14:00:00+00:00', '2026-11-09T17:28:00+00:00', 'Session 4'),
    ('ARC05', 'AFT', '2026-11-10T14:00:00+00:00', '2026-11-10T17:28:00+00:00', 'Session 5'),
    ('ARC06', 'MOR', '2026-11-11T10:00:00+00:00', '2026-11-11T11:44:00+00:00', 'Session 6'),
    ('ARC07', 'AFT', '2026-11-11T14:00:00+00:00', '2026-11-11T15:44:00+00:00', 'Session 7'),
    ('ARC08', 'MOR', '2026-11-12T10:00:00+00:00', '2026-11-12T11:44:00+00:00', 'Session 8'),
    ('ARC09', 'AFT', '2026-11-12T14:00:00+00:00', '2026-11-12T15:44:00+00:00', 'Session 9'),
]

# (unit_rsc, phase_type, unit_num, start, end, medal, order, session_code, item_name)
UNITS = [
    ('ARCWINDIVID-----------QUAL000100--', '3', '', '2026-11-07T09:30:00+00:00', '2026-11-07T12:30:00+00:00', '', '1', 'ARC01', "Women's Individual Ranking Round"),
    ('ARCMINDIVID-----------QUAL000100--', '3', '', '2026-11-07T09:30:00+00:00', '2026-11-07T12:30:00+00:00', '', '2', 'ARC01', "Men's Individual Ranking Round"),
    ('ARCXTEAM2-------------QUAL000100--', '3', '', '2026-11-07T09:30:00+00:00', '2026-11-07T12:30:00+00:00', '', '3', 'ARC01', 'Mixed Team Ranking Round'),
    ('ARCXTEAM2-------------8FNL000100--', '3', '1', '2026-11-08T09:30:00+00:00', '2026-11-08T09:53:00+00:00', '', '1', 'ARC02', 'Mixed Team 1/8 Elimination Round'),
    ('ARCXTEAM2-------------8FNL000200--', '3', '2', '2026-11-08T09:53:00+00:00', '2026-11-08T10:16:00+00:00', '', '2', 'ARC02', 'Mixed Team 1/8 Elimination Round'),
    ('ARCXTEAM2-------------8FNL000300--', '3', '3', '2026-11-08T10:16:00+00:00', '2026-11-08T10:39:00+00:00', '', '3', 'ARC02', 'Mixed Team 1/8 Elimination Round'),
    ('ARCXTEAM2-------------8FNL000400--', '3', '4', '2026-11-08T10:39:00+00:00', '2026-11-08T11:02:00+00:00', '', '4', 'ARC02', 'Mixed Team 1/8 Elimination Round'),
    ('ARCXTEAM2-------------8FNL000500--', '3', '5', '2026-11-08T11:02:00+00:00', '2026-11-08T11:25:00+00:00', '', '5', 'ARC02', 'Mixed Team 1/8 Elimination Round'),
    ('ARCXTEAM2-------------8FNL000600--', '3', '6', '2026-11-08T11:25:00+00:00', '2026-11-08T11:48:00+00:00', '', '6', 'ARC02', 'Mixed Team 1/8 Elimination Round'),
    ('ARCXTEAM2-------------8FNL000700--', '3', '7', '2026-11-08T11:48:00+00:00', '2026-11-08T12:11:00+00:00', '', '7', 'ARC02', 'Mixed Team 1/8 Elimination Round'),
    ('ARCXTEAM2-------------8FNL000800--', '3', '8', '2026-11-08T12:11:00+00:00', '2026-11-08T12:34:00+00:00', '', '8', 'ARC02', 'Mixed Team 1/8 Elimination Round'),
    ('ARCXTEAM2-------------QFNL000100--', '3', '9', '2026-11-08T14:00:00+00:00', '2026-11-08T14:23:00+00:00', '', '9', 'ARC03', 'Mixed Team Quarterfinal'),
    ('ARCXTEAM2-------------QFNL000200--', '3', '10', '2026-11-08T14:23:00+00:00', '2026-11-08T14:46:00+00:00', '', '10', 'ARC03', 'Mixed Team Quarterfinal'),
    ('ARCXTEAM2-------------QFNL000300--', '3', '11', '2026-11-08T14:46:00+00:00', '2026-11-08T15:09:00+00:00', '', '11', 'ARC03', 'Mixed Team Quarterfinal'),
    ('ARCXTEAM2-------------QFNL000400--', '3', '12', '2026-11-08T15:09:00+00:00', '2026-11-08T15:32:00+00:00', '', '12', 'ARC03', 'Mixed Team Quarterfinal'),
    ('ARCXTEAM2-------------SFNL000100--', '3', '13', '2026-11-08T15:32:00+00:00', '2026-11-08T15:55:00+00:00', '', '13', 'ARC03', 'Mixed Team Semifinal'),
    ('ARCXTEAM2-------------SFNL000200--', '3', '14', '2026-11-08T15:55:00+00:00', '2026-11-08T16:18:00+00:00', '', '14', 'ARC03', 'Mixed Team Semifinal'),
    ('ARCXTEAM2-------------FNL-000200--', '3', '15', '2026-11-08T16:18:00+00:00', '2026-11-08T16:41:00+00:00', '3', '15', 'ARC03', 'Mixed Team Bronze Medal Match'),
    ('ARCXTEAM2-------------FNL-000100--', '3', '16', '2026-11-08T16:41:00+00:00', '2026-11-08T17:04:00+00:00', '1', '16', 'ARC03', 'Mixed Team Gold Medal Match'),
    ('ARCWINDIVID-----------R32-000600--', '3', '17', '2026-11-09T14:00:00+00:00', '2026-11-09T14:13:00+00:00', '', '1', 'ARC04', "Women's Individual 1/16 Elimination Rnd"),
    ('ARCWINDIVID-----------R32-000500--', '3', '18', '2026-11-09T14:13:00+00:00', '2026-11-09T14:26:00+00:00', '', '2', 'ARC04', "Women's Individual 1/16 Elimination Rnd"),
    ('ARCMINDIVID-----------R32-000600--', '3', '19', '2026-11-09T14:26:00+00:00', '2026-11-09T14:39:00+00:00', '', '3', 'ARC04', "Men's Individual 1/16 Elimination Round"),
    ('ARCMINDIVID-----------R32-000500--', '3', '20', '2026-11-09T14:39:00+00:00', '2026-11-09T14:52:00+00:00', '', '4', 'ARC04', "Men's Individual 1/16 Elimination Round"),
    ('ARCWINDIVID-----------R32-000700--', '3', '21', '2026-11-09T14:52:00+00:00', '2026-11-09T15:05:00+00:00', '', '5', 'ARC04', "Women's Individual 1/16 Elimination Rnd"),
    ('ARCWINDIVID-----------R32-000800--', '3', '22', '2026-11-09T15:05:00+00:00', '2026-11-09T15:18:00+00:00', '', '6', 'ARC04', "Women's Individual 1/16 Elimination Rnd"),
    ('ARCMINDIVID-----------R32-000700--', '3', '23', '2026-11-09T15:18:00+00:00', '2026-11-09T15:31:00+00:00', '', '7', 'ARC04', "Men's Individual 1/16 Elimination Round"),
    ('ARCMINDIVID-----------R32-000800--', '3', '24', '2026-11-09T15:31:00+00:00', '2026-11-09T15:44:00+00:00', '', '8', 'ARC04', "Men's Individual 1/16 Elimination Round"),
    ('ARCWINDIVID-----------R32-001100--', '3', '25', '2026-11-09T15:44:00+00:00', '2026-11-09T15:57:00+00:00', '', '9', 'ARC04', "Women's Individual 1/16 Elimination Rnd"),
    ('ARCWINDIVID-----------R32-001200--', '3', '26', '2026-11-09T15:57:00+00:00', '2026-11-09T16:10:00+00:00', '', '10', 'ARC04', "Women's Individual 1/16 Elimination Rnd"),
    ('ARCMINDIVID-----------R32-001100--', '3', '27', '2026-11-09T16:10:00+00:00', '2026-11-09T16:23:00+00:00', '', '11', 'ARC04', "Men's Individual 1/16 Elimination Round"),
    ('ARCMINDIVID-----------R32-001200--', '3', '28', '2026-11-09T16:23:00+00:00', '2026-11-09T16:36:00+00:00', '', '12', 'ARC04', "Men's Individual 1/16 Elimination Round"),
    ('ARCWINDIVID-----------R32-001000--', '3', '29', '2026-11-09T16:36:00+00:00', '2026-11-09T16:49:00+00:00', '', '13', 'ARC04', "Women's Individual 1/16 Elimination Rnd"),
    ('ARCWINDIVID-----------R32-000900--', '3', '30', '2026-11-09T16:49:00+00:00', '2026-11-09T17:02:00+00:00', '', '14', 'ARC04', "Women's Individual 1/16 Elimination Rnd"),
    ('ARCMINDIVID-----------R32-001000--', '3', '31', '2026-11-09T17:02:00+00:00', '2026-11-09T17:15:00+00:00', '', '15', 'ARC04', "Men's Individual 1/16 Elimination Round"),
    ('ARCMINDIVID-----------R32-000900--', '3', '32', '2026-11-09T17:15:00+00:00', '2026-11-09T17:28:00+00:00', '', '16', 'ARC04', "Men's Individual 1/16 Elimination Round"),
    ('ARCWINDIVID-----------R32-001400--', '3', '33', '2026-11-10T14:00:00+00:00', '2026-11-10T14:13:00+00:00', '', '1', 'ARC05', "Women's Individual 1/16 Elimination Rnd"),
    ('ARCWINDIVID-----------R32-001300--', '3', '34', '2026-11-10T14:13:00+00:00', '2026-11-10T14:26:00+00:00', '', '2', 'ARC05', "Women's Individual 1/16 Elimination Rnd"),
    ('ARCMINDIVID-----------R32-001400--', '3', '35', '2026-11-10T14:26:00+00:00', '2026-11-10T14:39:00+00:00', '', '3', 'ARC05', "Men's Individual 1/16 Elimination Round"),
    ('ARCMINDIVID-----------R32-001300--', '3', '36', '2026-11-10T14:39:00+00:00', '2026-11-10T14:52:00+00:00', '', '4', 'ARC05', "Men's Individual 1/16 Elimination Round"),
    ('ARCWINDIVID-----------R32-001500--', '3', '37', '2026-11-10T14:52:00+00:00', '2026-11-10T15:05:00+00:00', '', '5', 'ARC05', "Women's Individual 1/16 Elimination Rnd"),
    ('ARCWINDIVID-----------R32-001600--', '3', '38', '2026-11-10T15:05:00+00:00', '2026-11-10T15:18:00+00:00', '', '6', 'ARC05', "Women's Individual 1/16 Elimination Rnd"),
    ('ARCMINDIVID-----------R32-001500--', '3', '39', '2026-11-10T15:18:00+00:00', '2026-11-10T15:31:00+00:00', '', '7', 'ARC05', "Men's Individual 1/16 Elimination Round"),
    ('ARCMINDIVID-----------R32-001600--', '3', '40', '2026-11-10T15:31:00+00:00', '2026-11-10T15:44:00+00:00', '', '8', 'ARC05', "Men's Individual 1/16 Elimination Round"),
    ('ARCWINDIVID-----------R32-000300--', '3', '41', '2026-11-10T15:44:00+00:00', '2026-11-10T15:57:00+00:00', '', '9', 'ARC05', "Women's Individual 1/16 Elimination Rnd"),
    ('ARCWINDIVID-----------R32-000400--', '3', '42', '2026-11-10T15:57:00+00:00', '2026-11-10T16:10:00+00:00', '', '10', 'ARC05', "Women's Individual 1/16 Elimination Rnd"),
    ('ARCMINDIVID-----------R32-000300--', '3', '43', '2026-11-10T16:10:00+00:00', '2026-11-10T16:23:00+00:00', '', '11', 'ARC05', "Men's Individual 1/16 Elimination Round"),
    ('ARCMINDIVID-----------R32-000400--', '3', '44', '2026-11-10T16:23:00+00:00', '2026-11-10T16:36:00+00:00', '', '12', 'ARC05', "Men's Individual 1/16 Elimination Round"),
    ('ARCWINDIVID-----------R32-000200--', '3', '45', '2026-11-10T16:36:00+00:00', '2026-11-10T16:49:00+00:00', '', '13', 'ARC05', "Women's Individual 1/16 Elimination Rnd"),
    ('ARCWINDIVID-----------R32-000100--', '3', '46', '2026-11-10T16:49:00+00:00', '2026-11-10T17:02:00+00:00', '', '14', 'ARC05', "Women's Individual 1/16 Elimination Rnd"),
    ('ARCMINDIVID-----------R32-000200--', '3', '47', '2026-11-10T17:02:00+00:00', '2026-11-10T17:15:00+00:00', '', '15', 'ARC05', "Men's Individual 1/16 Elimination Round"),
    ('ARCMINDIVID-----------R32-000100--', '3', '48', '2026-11-10T17:15:00+00:00', '2026-11-10T17:28:00+00:00', '', '16', 'ARC05', "Men's Individual 1/16 Elimination Round"),
    ('ARCWINDIVID-----------8FNL000200--', '3', '49', '2026-11-11T10:00:00+00:00', '2026-11-11T10:13:00+00:00', '', '1', 'ARC06', "Women's Individual 1/8 Elimination Round"),
    ('ARCWINDIVID-----------8FNL000300--', '3', '50', '2026-11-11T10:13:00+00:00', '2026-11-11T10:26:00+00:00', '', '2', 'ARC06', "Women's Individual 1/8 Elimination Round"),
    ('ARCWINDIVID-----------8FNL000400--', '3', '51', '2026-11-11T10:26:00+00:00', '2026-11-11T10:39:00+00:00', '', '3', 'ARC06', "Women's Individual 1/8 Elimination Round"),
    ('ARCWINDIVID-----------8FNL000100--', '3', '52', '2026-11-11T10:39:00+00:00', '2026-11-11T10:52:00+00:00', '', '4', 'ARC06', "Women's Individual 1/8 Elimination Round"),
    ('ARCWINDIVID-----------8FNL000700--', '3', '53', '2026-11-11T10:52:00+00:00', '2026-11-11T11:05:00+00:00', '', '5', 'ARC06', "Women's Individual 1/8 Elimination Round"),
    ('ARCWINDIVID-----------8FNL000600--', '3', '54', '2026-11-11T11:05:00+00:00', '2026-11-11T11:18:00+00:00', '', '6', 'ARC06', "Women's Individual 1/8 Elimination Round"),
    ('ARCWINDIVID-----------8FNL000500--', '3', '55', '2026-11-11T11:18:00+00:00', '2026-11-11T11:31:00+00:00', '', '7', 'ARC06', "Women's Individual 1/8 Elimination Round"),
    ('ARCWINDIVID-----------8FNL000800--', '3', '56', '2026-11-11T11:31:00+00:00', '2026-11-11T11:44:00+00:00', '', '8', 'ARC06', "Women's Individual 1/8 Elimination Round"),
    ('ARCWINDIVID-----------QFNL000200--', '3', '57', '2026-11-11T14:00:00+00:00', '2026-11-11T14:13:00+00:00', '', '9', 'ARC07', "Women's Individual Quarterfinal"),
    ('ARCWINDIVID-----------QFNL000100--', '3', '58', '2026-11-11T14:13:00+00:00', '2026-11-11T14:26:00+00:00', '', '10', 'ARC07', "Women's Individual Quarterfinal"),
    ('ARCWINDIVID-----------QFNL000300--', '3', '59', '2026-11-11T14:26:00+00:00', '2026-11-11T14:39:00+00:00', '', '11', 'ARC07', "Women's Individual Quarterfinal"),
    ('ARCWINDIVID-----------QFNL000400--', '3', '60', '2026-11-11T14:39:00+00:00', '2026-11-11T14:52:00+00:00', '', '12', 'ARC07', "Women's Individual Quarterfinal"),
    ('ARCWINDIVID-----------SFNL000100--', '3', '61', '2026-11-11T14:52:00+00:00', '2026-11-11T15:05:00+00:00', '', '13', 'ARC07', "Women's Individual Semifinal"),
    ('ARCWINDIVID-----------SFNL000200--', '3', '62', '2026-11-11T15:05:00+00:00', '2026-11-11T15:18:00+00:00', '', '14', 'ARC07', "Women's Individual Semifinal"),
    ('ARCWINDIVID-----------FNL-000200--', '3', '63', '2026-11-11T15:18:00+00:00', '2026-11-11T15:31:00+00:00', '3', '15', 'ARC07', "Women's Individual Bronze Medal Match"),
    ('ARCWINDIVID-----------FNL-000100--', '3', '64', '2026-11-11T15:31:00+00:00', '2026-11-11T15:44:00+00:00', '1', '16', 'ARC07', "Women's Individual Gold Medal Match"),
    ('ARCMINDIVID-----------8FNL000200--', '3', '65', '2026-11-12T10:00:00+00:00', '2026-11-12T10:13:00+00:00', '', '1', 'ARC08', "Men's Individual 1/8 Elimination Round"),
    ('ARCMINDIVID-----------8FNL000300--', '3', '66', '2026-11-12T10:13:00+00:00', '2026-11-12T10:26:00+00:00', '', '2', 'ARC08', "Men's Individual 1/8 Elimination Round"),
    ('ARCMINDIVID-----------8FNL000400--', '3', '67', '2026-11-12T10:26:00+00:00', '2026-11-12T10:39:00+00:00', '', '3', 'ARC08', "Men's Individual 1/8 Elimination Round"),
    ('ARCMINDIVID-----------8FNL000100--', '3', '68', '2026-11-12T10:39:00+00:00', '2026-11-12T10:52:00+00:00', '', '4', 'ARC08', "Men's Individual 1/8 Elimination Round"),
    ('ARCMINDIVID-----------8FNL000700--', '3', '69', '2026-11-12T10:52:00+00:00', '2026-11-12T11:05:00+00:00', '', '5', 'ARC08', "Men's Individual 1/8 Elimination Round"),
    ('ARCMINDIVID-----------8FNL000600--', '3', '70', '2026-11-12T11:05:00+00:00', '2026-11-12T11:18:00+00:00', '', '6', 'ARC08', "Men's Individual 1/8 Elimination Round"),
    ('ARCMINDIVID-----------8FNL000500--', '3', '71', '2026-11-12T11:18:00+00:00', '2026-11-12T11:31:00+00:00', '', '7', 'ARC08', "Men's Individual 1/8 Elimination Round"),
    ('ARCMINDIVID-----------8FNL000800--', '3', '72', '2026-11-12T11:31:00+00:00', '2026-11-12T11:44:00+00:00', '', '8', 'ARC08', "Men's Individual 1/8 Elimination Round"),
    ('ARCMINDIVID-----------QFNL000200--', '3', '73', '2026-11-12T14:00:00+00:00', '2026-11-12T14:13:00+00:00', '', '9', 'ARC09', "Men's Individual Quarterfinal"),
    ('ARCMINDIVID-----------QFNL000100--', '3', '74', '2026-11-12T14:13:00+00:00', '2026-11-12T14:26:00+00:00', '', '10', 'ARC09', "Men's Individual Quarterfinal"),
    ('ARCMINDIVID-----------QFNL000300--', '3', '75', '2026-11-12T14:26:00+00:00', '2026-11-12T14:39:00+00:00', '', '11', 'ARC09', "Men's Individual Quarterfinal"),
    ('ARCMINDIVID-----------QFNL000400--', '3', '76', '2026-11-12T14:39:00+00:00', '2026-11-12T14:52:00+00:00', '', '12', 'ARC09', "Men's Individual Quarterfinal"),
    ('ARCMINDIVID-----------SFNL000100--', '3', '77', '2026-11-12T14:52:00+00:00', '2026-11-12T15:05:00+00:00', '', '13', 'ARC09', "Men's Individual Semifinal"),
    ('ARCMINDIVID-----------SFNL000200--', '3', '78', '2026-11-12T15:05:00+00:00', '2026-11-12T15:18:00+00:00', '', '14', 'ARC09', "Men's Individual Semifinal"),
    ('ARCMINDIVID-----------FNL-000200--', '3', '79', '2026-11-12T15:18:00+00:00', '2026-11-12T15:31:00+00:00', '3', '15', 'ARC09', "Men's Individual Bronze Medal Match"),
    ('ARCMINDIVID-----------FNL-000100--', '3', '80', '2026-11-12T15:31:00+00:00', '2026-11-12T15:44:00+00:00', '1', '16', 'ARC09', "Men's Individual Gold Medal Match"),
]
