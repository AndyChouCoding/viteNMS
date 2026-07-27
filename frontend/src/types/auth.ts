export type Role = "viewer" | "operator" | "admin"

export interface User {
  id: number
  username: string
  role: Role
}

export interface LoginResponse {
  token: string
  user: User
}
