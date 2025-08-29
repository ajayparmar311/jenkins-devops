import http from "k6/http";
import { check, sleep } from "k6";

export const options = {
  vus: 10,          // number of virtual users
  duration: "30s",  // how long to run test
};

const url = "http://localhost:5000/log";  // 👈 Important!
const headers = { "Content-Type": "application/json" };
const payload = JSON.stringify({
  app_info: "CAMERACART-UI",
  message_id: "LOG_ERROR",
  event: "STATE_ERROR",
  event_value: "CAM_ID : 123",
});

export default function () {
  let res = http.post(url, payload, { headers });
  check(res, { "status is 200": (r) => r.status === 200 });
  sleep(1);
}
