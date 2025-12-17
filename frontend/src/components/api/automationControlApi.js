import { get, patch } from './httpClient';

export function fetchAutomationControl() {
  return get('/automation-control/');
}

export function updateAutomationControl(enabled) {
  return patch('/automation-control/1/', { enabled });
}
