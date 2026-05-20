// order-ai-share: no portal auth. Single-brand standalone fork.
// Hook 이름은 호출처 호환 위해 유지 (AuthContext 가 그대로 import).
//
// role 값은 BACKEND 가 무시하지만, 프론트의 hasRole/hasAnyRole 호환을 위해 'all' 부여.

const SHARE_USER = {
  id: 'share-user',
  name: 'Brand Operator',
  email: 'operator@local',
  image: null,
  role: ['orderai:brand:all'],
}

export function useDcsAuth() {
  return { user: SHARE_USER, isLoading: false }
}
