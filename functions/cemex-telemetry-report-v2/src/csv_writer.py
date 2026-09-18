from __future__ import annotations

import csv
import io

from constants import (
    CSV_HEADERS_EN,
    CSV_HEADERS_ES,
    CSV_HEADERS_TRACKING,
    EN_CSV_DELIMITER,
    ES_CSV_DELIMITER,
    UTF8_BOM,
)
from models import AlignedRow
from transform import row_to_cells


def csv_headers(dialect: str) -> tuple[str, ...]:
    if dialect == "tracking":
        return CSV_HEADERS_TRACKING
    return CSV_HEADERS_EN if dialect == "en" else CSV_HEADERS_ES


def render_csv(rows: list[AlignedRow], timezone: str, dialect: str) -> bytes:
    buffer = io.StringIO()
    delimiter = ES_CSV_DELIMITER if dialect == "es" else EN_CSV_DELIMITER
    quoting = csv.QUOTE_ALL if dialect == "es" else csv.QUOTE_MINIMAL
    writer = csv.writer(buffer, delimiter=delimiter, lineterminator="\n", quoting=quoting)
    writer.writerow(list(csv_headers(dialect)))
    for row in rows:
        writer.writerow(row_to_cells(row, timezone, dialect))
    body = buffer.getvalue().encode("utf-8")
    if dialect == "tracking":
        return body
    return UTF8_BOM + body
