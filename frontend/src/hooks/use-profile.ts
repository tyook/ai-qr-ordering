import { useQuery, useMutation, useQueryClient } from "@tanstack/react-query";
import { fetchMe, updateProfile } from "@/lib/api";

export function useProfile() {
  return useQuery({
    queryKey: ["profile"],
    queryFn: fetchMe,
  });
}

export function useUpdateProfile() {
  const queryClient = useQueryClient();
  return useMutation({
    mutationFn: updateProfile,
    onSuccess: () => {
      queryClient.invalidateQueries({ queryKey: ["profile"] });
    },
  });
}
