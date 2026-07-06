
import {
  API_URL,
  ApiError,
  apiFetch,
  apiJson,
  ensureFreshAccess,
  getAccessToken,
} from "./client.js";

const json = (body) => ({
  headers: { "Content-Type": "application/json" },
  body: JSON.stringify(body),
});


export const fetchMe = () => apiJson("/api/me");


export function listFiles({ pageToken, folderId, pageSize = 50 } = {}) {
  const params = new URLSearchParams({ page_size: String(pageSize) });
  if (pageToken) params.set("page_token", pageToken);
  if (folderId) params.set("folder_id", folderId);
  return apiJson(`/api/files?${params}`);
}


export async function downloadFile(file) {
  const res = await apiFetch(`/api/files/${encodeURIComponent(file.id)}/content`);
  const blob = await res.blob();
  const url = URL.createObjectURL(blob);
  const anchor = document.createElement("a");
  anchor.href = url;
  anchor.download = file.name || "download";
  document.body.appendChild(anchor);
  anchor.click();
  anchor.remove();
  URL.revokeObjectURL(url);
}


export async function uploadFile(file, { folderId, onProgress } = {}) {
  await ensureFreshAccess();
  return new Promise((resolve, reject) => {
    const xhr = new XMLHttpRequest();
    xhr.open("POST", `${API_URL}/api/files`);
    xhr.setRequestHeader("Authorization", `Bearer ${getAccessToken()}`);
    xhr.upload.onprogress = (event) => {
      if (event.lengthComputable && onProgress) {
        onProgress(Math.round((event.loaded / event.total) * 100));
      }
    };
    xhr.onload = () => {
      let body = null;
      try {
        body = JSON.parse(xhr.responseText);
      } catch {}
      if (xhr.status >= 200 && xhr.status < 300) resolve(body);
      else reject(new ApiError(body, xhr.status));
    };
    xhr.onerror = () => reject(new ApiError(null, 0));
    const form = new FormData();
    form.append("file", file);
    if (folderId) form.append("folder_id", folderId);
    xhr.send(form);
  });
}


export const listTeams = () => apiJson("/api/admin/teams");
export const createTeam = (data) => apiJson("/api/admin/teams", { method: "POST", ...json(data) });
export const updateTeam = (id, data) =>
  apiJson(`/api/admin/teams/${id}`, { method: "PATCH", ...json(data) });
export const deleteTeam = (id) => apiFetch(`/api/admin/teams/${id}`, { method: "DELETE" });
export const addMember = (teamId, userId) =>
  apiJson(`/api/admin/teams/${teamId}/members`, { method: "POST", ...json({ user_id: userId }) });
export const removeMember = (teamId, userId) =>
  apiJson(`/api/admin/teams/${teamId}/members`, { method: "DELETE", ...json({ user_id: userId }) });
export const listUsers = () => apiJson("/api/admin/users");


export const listCredentials = () => apiJson("/api/admin/credentials");
export const createServiceAccountCredential = (data) =>
  apiJson("/api/admin/credentials", { method: "POST", ...json(data) });
export const initiateOAuth = (accountLabel) =>
  apiJson("/api/admin/credentials/oauth/initiate", {
    method: "POST",
    ...json(accountLabel ? { account_label: accountLabel } : {}),
  });
export const activateCredential = (id) =>
  apiJson(`/api/admin/credentials/${id}/activate`, { method: "POST" });
export const getPermissionMatrix = (id) => apiJson(`/api/admin/credentials/${id}/permissions`);
export const savePermissionMatrix = (id, rows) =>
  apiJson(`/api/admin/credentials/${id}/permissions`, {
    method: "PUT",
    ...json({ permissions: rows }),
  });
