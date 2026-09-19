"""ApprovalHook: pausa send_email hasta que un humano lo aprueba. La tool no sabe que existe."""
from strands.hooks import BeforeToolCallEvent, HookProvider, HookRegistry


class ApprovalHook(HookProvider):
    def __init__(self, app_name: str) -> None:
        self.app_name = app_name

    # El UNICO punto de contacto con el SDK: una suscripcion.
    def register_hooks(self, registry: HookRegistry) -> None:
        registry.add_callback(BeforeToolCallEvent, self.approve)

    def approve(self, event: BeforeToolCallEvent) -> None:
        # Este chequeo se reejecuta entero en cada reanudacion: barato y sin efectos de lado.
        if event.tool_use["name"] != "send_email":
            return
        # Bloquea aqui: si nadie ha respondido todavia, interrupt() lanza y el turno se detiene.
        approval = event.interrupt(f"{self.app_name}-approval", reason=event.tool_use["input"])
        if approval.strip().lower() != "y":
            event.cancel_tool = "User denied permission to send the email"
