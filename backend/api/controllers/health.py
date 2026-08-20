from rest_framework.response import Response
from rest_framework.views import APIView


class HealthController(APIView):
    """Liveness probe for orchestrators and load balancers.

    Controller only, deliberately no Facade — it must never fail because of
    domain-layer wiring.
    """

    def get(self, request):
        return Response({"status": "ok"})
