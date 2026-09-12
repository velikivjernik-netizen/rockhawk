import time

from app.jobs import process_one_from_redis


def main() -> None:
    print("RockHawk worker listening for jobs", flush=True)
    while True:
        try:
            if not process_one_from_redis():
                time.sleep(0.5)
        except Exception as exc:  # noqa: BLE001
            print(f"worker error: {exc}", flush=True)
            time.sleep(2)


if __name__ == "__main__":
    main()
