import { get } from "../api/httpClient";

export function fetchDeposits({ search, page = 1 } = {}) {
  return get("/account-transactions/", { search, page });
}