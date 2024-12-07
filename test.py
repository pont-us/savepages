import savepages
import datetime


def test_parse_availability():
    timestamp = datetime.datetime(
        2018, 4, 27, 13, 6, 34, tzinfo=datetime.timezone.utc
    )
    response = {
        "url": "http://tc.eserver.org/",
        "archived_snapshots": {
            "closest": {
                "status": "200",
                "available": True,
                "url": "http://web.archive.org/web/20180427130634/https://tc.eserver.org/",
                "timestamp": timestamp.strftime("%Y%m%d%H%M%S"),
            }
        },
    }
    current_delta = datetime.datetime.now(tz=datetime.timezone.utc) - timestamp
    assert abs(
        savepages.parse_availability(response) - current_delta
    ) < datetime.timedelta(seconds=1)
