import os
from dotenv import load_dotenv
from strands import Agent, tool
from strands.models.openai_responses import OpenAIResponsesModel
from approval import ApprovalHook
# Lee el .env local: la clave (que toma el cliente de openai) y el modelo.
load_dotenv()
MODEL_ID = os.getenv("MODEL_ID", "gpt-6-luna")

SYSTEM_PROMPT = """You are Mailbot, an email drafting assistant.

Always draft an email with draft_email before sending it. Only call
send_email once you have a draft the user is happy with.

If a tool reports an error, tell the user plainly what went wrong."""
# El buzon entero cabe en dos estructuras: nada de esto sobrevive al proceso.
DRAFTS, SENT = {}, []
# Ids deterministas, no aleatorios: el transcript del README sigue siendo cierto manana.
_NEXT_MESSAGE_ID = iter(["MSG-4471", "MSG-4472", "MSG-4473"])

@tool
def draft_email(to: str, subject: str, body: str) -> str:
    """Write an email draft for a recipient. Does not send anything.

    Args:
        to: The recipient email address, e.g. "boss@example.com".
        subject: The subject line of the email.
        body: The body text of the email.
    """
    DRAFTS[to] = {"to": to, "subject": subject, "body": body}
    return f"Draft ready for {to}: subject '{subject}'."

@tool
def send_email(to: str, subject: str, body: str) -> str:
    """Send an email that was drafted first. Returns the message id, or an error
    message if there is no draft for the recipient.

    Args:
        to: The recipient email address, e.g. "boss@example.com".
        subject: The subject line of the email.
        body: The body text of the email.
    """
    # Los errores se devuelven como texto: el modelo los lee y se corrige en el mismo turno.
    if to not in DRAFTS:
        return f"No draft for '{to}'. Call draft_email first."
    SENT.append({"to": to, "subject": subject, "body": body})
    return f"Sent to {to}. Message id: {next(_NEXT_MESSAGE_ID, 'MSG-9999')}."

# El agente: identico al de 10 salvo por QUE hace el hook — aqui decide, no solo mira.
agent = Agent(
    model=OpenAIResponsesModel(model_id=MODEL_ID),
    system_prompt=SYSTEM_PROMPT,
    tools=[draft_email, send_email],
    hooks=[ApprovalHook("mailer")],
    # Sin esto, el PrintingCallbackHandler se intercala con el prompt de aprobacion: ver README.
    callback_handler=None,
)

def _resolve_interrupts(result):
    # Reanudar NO es un prompt nuevo: es una lista de interruptResponse contra el mismo turno.
    while result.stop_reason == "interrupt":
        responses = []
        for itr in result.interrupts:
            print(f"\n[approval] {itr.name}")
            for key, value in itr.reason.items():
                print(f"  {key}: {value}")
            answer = input("  Approve sending? (y/n): ")
            responses.append({"interruptResponse": {"interruptId": itr.id, "response": answer}})
        result = agent(responses)
    return result

if __name__ == "__main__":
    print(f"\nMailbot: email assistant ({MODEL_ID}). Type 'exit' to quit.")

    while True:
        user_input = input("\nYou > ")
        if user_input.lower() == "exit":
            break
        response = _resolve_interrupts(agent(user_input))
        print(f"\nMailbot > {response}")
