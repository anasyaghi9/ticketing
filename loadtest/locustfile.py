import json
import random
from itertools import count

from locust import HttpUser, between, task

with open("/mnt/locust/tokens.json") as f:
    DATA = json.load(f)

EVENT_ID = DATA["event_id"]
SEAT_IDS = DATA["seat_ids"]
TOKENS = DATA["tokens"]
next_user = count()


class Attendee(HttpUser):
    wait_time = between(0.5, 1.5)

    def on_start(self):
        self.token = TOKENS[next(next_user) % len(TOKENS)]

    @task(5)
    def list_events(self):
        self.client.get("/api/events/")

    @task(3)
    def view_event(self):
        self.client.get(f"/api/events/{EVENT_ID}/", name="/api/events/[id]/")

    @task(2)
    def book_random_seat(self):
        seat_id = random.choice(SEAT_IDS)
        with self.client.post(
            f"/api/events/seats/{seat_id}/book/",
            headers={"Authorization": f"Bearer {self.token}"},
            name="/api/events/seats/[id]/book/",
            catch_response=True,
        ) as response:
            # 201 = got the seat, 409 = someone else did. Both are correct.
            if response.status_code in (201, 409):
                response.success()
            else:
                response.failure(f"unexpected status {response.status_code}")