from rest_framework import status
from rest_framework.permissions import IsAuthenticated
from rest_framework.response import Response
from rest_framework.views import APIView


class OnboardingCompleteView(APIView):
    permission_classes = [IsAuthenticated]

    def post(self, request):
        request.user.onboarding_completed = True
        request.user.save(update_fields=["onboarding_completed"])
        return Response({"status": "ok"}, status=status.HTTP_200_OK)


class OnboardingDismissView(APIView):
    permission_classes = [IsAuthenticated]

    def post(self, request):
        request.user.onboarding_dismissed = True
        request.user.save(update_fields=["onboarding_dismissed"])
        return Response({"status": "ok"}, status=status.HTTP_200_OK)
