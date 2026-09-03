from ..config import ServiceRoute, settings


class RouterService:
    def resolve(self, path: str) -> ServiceRoute:
        for route in settings.routes:
            gateway_prefix = f"/{route.name}"
            if path == gateway_prefix or path.startswith(f"{gateway_prefix}/"):
                return route
        raise KeyError("URL, servis adıyla başlamalıdır: /market-service veya /model-service")

    @staticmethod
    def upstream_path(path: str, route: ServiceRoute) -> str:
        stripped = path[len(f"/{route.name}"):]
        return stripped or "/"

    @staticmethod
    def timeout_for(upstream_path: str) -> float:
        """Üst servis okuma süresi: yavaş olduğu bilinen yollar (eğitim) uzun, kalanı kısa."""
        slow = any(upstream_path == p or upstream_path.startswith(f"{p}/") for p in settings.slow_prefixes)
        return settings.slow_timeout if slow else settings.upstream_timeout

    def describe(self) -> list[dict]:
        return [{"service": route.name, "gateway_prefix": f"/{route.name}",
                 "base_url": route.base_url, "upstream_prefixes": route.prefixes} for route in settings.routes]


router_service = RouterService()
