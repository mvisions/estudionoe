import { createContext, useContext, useEffect, useState } from 'react';
import pb from '../lib/pocketbase';

const AuthContext = createContext(null);

export function AuthProvider({ children }) {
  const [user, setUser] = useState(pb.authStore.model);
  const [loading, setLoading] = useState(true);

  useEffect(() => {
    const unsubscribe = pb.authStore.onChange(() => {
      setUser(pb.authStore.model);
    });
    setLoading(false);
    return () => unsubscribe();
  }, []);

  const login = async (email, password) => {
    const authData = await pb.collection('users').authWithPassword(email, password);
    setUser(authData.record);
    return authData.record;
  };

  const logout = () => {
    pb.authStore.clear();
    setUser(null);
  };

  const isAdmin = user?.role === 'admin';
  const isFarmacia = user?.role === 'farmacia';

  return (
    <AuthContext.Provider value={{ user, login, logout, isAdmin, isFarmacia, loading }}>
      {children}
    </AuthContext.Provider>
  );
}

export const useAuth = () => useContext(AuthContext);
