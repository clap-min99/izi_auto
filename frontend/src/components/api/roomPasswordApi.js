import { get, post, patch } from "./httpClient";

export function fetchRoomPasswords() {
  return get("/room-passwords/");
}

export function createRoomPassword(payload) {
  // payload: { room_name, room_pw }
  return post("/room-passwords/", payload);
}

export function updateRoomPassword(id, payload) {
  // payload: { room_pw }
  return patch(`/room-passwords/${id}/`, payload);
}
