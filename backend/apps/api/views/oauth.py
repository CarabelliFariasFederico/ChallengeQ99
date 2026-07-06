from django.conf import settings
from django.http import HttpResponseRedirect
from rest_framework.exceptions import ValidationError
from rest_framework.permissions import AllowAny, IsAuthenticated
from rest_framework.response import Response
from rest_framework.views import APIView

from apps.api.permissions import IsAdministrator
from apps.application import oauth


class OAuthInitiateView(APIView):
    permission_classes = [IsAuthenticated, IsAdministrator]

    def post(self, request):
        payload = oauth.start_connection(request, request.data.get("account_label"))
        return Response(payload)


class OAuthCallbackView(APIView):
    authentication_classes = []
    permission_classes = [AllowAny]

    def get(self, request):
        state = oauth.consume_state(request.query_params.get("state", ""))

        error = request.query_params.get("error")
        if error:
            raise ValidationError(
                {
                    "error": f"Google returned '{error}'. The account was NOT connected — "
                    f"restart the connection and grant consent."
                }
            )
        code = request.query_params.get("code", "")
        if not code:
            raise ValidationError({"code": "Missing authorization code."})

        credential = oauth.complete_connection(request, state, code)
        return HttpResponseRedirect(
            f"{settings.FRONTEND_URL}/admin?drive_connected=1&credential_id={credential.pk}"
        )
