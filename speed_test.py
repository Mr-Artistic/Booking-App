# speed_test.py
import cProfile
import pstats
import io
import pandas as pd
from datetime import datetime, time, date, timedelta


from resource_app.functions import build_vertical_day_time_timeline


def make_sample_df(n=200):
    """Creates a small synthetic dataframe matching get_bookings() output shape."""
    rows = []
    base_date = date.today()
    for i in range(n):
        booking_date = base_date + timedelta(days=(i % 28))
        start = time(9 + (i % 8), 0, 0)  # 9:00..16:00
        end = time((start.hour + 1) % 24, 0, 0)
        resource_type = "ResourceA, ResourceB" if i % 3 == 0 else "ResourceA"
        rows.append(
            {
                "id": i + 1,
                "booking_date": booking_date,
                "start_time": start.strftime("%H:%M:%S"),
                "end_time": end.strftime("%H:%M:%S"),
                "resource_type": resource_type,
                "person_name": f"User{i}",
                "company_name": "Acme",
                "affiliation": "I-HUB",
                "email": f"user{i}@example.com",
                "created_at": pd.Timestamp.utcnow(),
            }
        )
    return pd.DataFrame(rows)


def main():
    # Builds synthetic data (avoid DB/network)
    df = make_sample_df(500)  # adjust size to stress-test vs keep quick

    # Profiles the call
    profiler = cProfile.Profile()
    profiler.enable()

    # Calls the function under test:
    fig, info = build_vertical_day_time_timeline(df)

    profiler.disable()

    # Print stats to stdout
    s = io.StringIO()
    ps = pstats.Stats(profiler, stream=s).strip_dirs().sort_stats("cumtime")
    ps.print_stats(40)  # show top 40 lines
    print(s.getvalue())

    # Save binary .prof file for GUI viewers
    profiler.dump_stats("speed_test.prof")
    print("Wrote speed_test.prof (open with snakeviz or pstats).")
    print("Returned info summary:", info)


if __name__ == "__main__":
    main()
