class HealthCheckMiddleware:
    """ALB health check の Host ヘッダー（タスクのプライベート IP）を localhost に書き換える。
    SecurityMiddleware より前に配置すること。
    """

    HEALTH_PATH = '/api/health/'

    def __init__(self, get_response):
        self.get_response = get_response

    def __call__(self, request):
        if request.path == self.HEALTH_PATH:
            request.META['HTTP_HOST'] = 'localhost'
        return self.get_response(request)
