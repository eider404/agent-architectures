import os
from datetime import date
from pathlib import Path
from typing import Literal
from dotenv import load_dotenv
from pydantic import BaseModel, Field, model_validator
from strands import Agent
from strands.models.openai_responses import OpenAIResponsesModel
# Lee el .env local: la clave (que toma el cliente de openai) y el modelo.
load_dotenv()
MODEL_ID = os.getenv("MODEL_ID", "gpt-5.4-mini")
# Ruta absoluta: el ejemplo se puede lanzar desde cualquier cwd.
SANDBOX = Path(__file__).parent / "sandbox"
class LineItem(BaseModel):
    """One billed line of an invoice."""
    description: str = Field(description="What was billed, as printed on the line.")
    quantity: int = Field(ge=1, description="Units billed, as an integer.")
    unit_price: float = Field(ge=0, description="Price of one unit, in the invoice currency.")

class Invoice(BaseModel):
    """An invoice extracted from a plain-text document."""
    invoice_id: str = Field(description="The invoice number as printed, e.g. 'INV-8842'.")
    supplier: str = Field(description="Name of the company that issued the invoice.")
    issued_on: date = Field(description="The issue date. Convert any printed format to ISO.")
    currency: Literal["EUR", "USD"] = Field(description="Currency of every amount.")
    items: list[LineItem] = Field(min_length=1, description=(
        "Every charge that contributes to the total, including shipping or handling "
        "fees printed outside the line table."))
    total: float = Field(ge=0, description="The amount due.")
    # Este cuerpo NO viaja al LLM: solo lo hace su mensaje de error, y solo si falla.
    # Por eso esta escrito como una instruccion, no como un diagnostico.
    @model_validator(mode="after")
    def total_matches_items(self) -> "Invoice":
        expected = round(sum(i.quantity * i.unit_price for i in self.items), 2)
        if abs(self.total - expected) > 0.01:
            raise ValueError(
                f"total is {self.total} but the {len(self.items)} items add up to {expected}. "
                f"Re-read the document: a charge included in the total is missing from items.")
        return self
SYSTEM_PROMPT = """You are Ledger, an invoice extraction service.

Read the invoice you are given and report it as structured data. Copy what the
document says; never invent a value that is not printed. Every charge that the
total includes must appear as a line item, even if the document prints it
outside the table of lines."""

# El agente: el de 01 sin herramientas. Lo unico nuevo esta en la llamada.
agent = Agent(model=OpenAIResponsesModel(model_id=MODEL_ID),
              system_prompt=SYSTEM_PROMPT, callback_handler=None)

def extract(filename: str) -> Invoice:
    """Extrae una factura de sandbox/ y devuelve el objeto validado."""
    document = (SANDBOX / filename).read_text()
    # Como en 05: el agente es una constante de modulo y acumula historial.
    agent.messages.clear()

    invoice = agent(document, structured_output_model=Invoice).structured_output

    # Atributos de Python, no texto: eso es todo lo que demuestra este ejemplo.
    print(f"\n[ok] {invoice.invoice_id} · {invoice.supplier} · "
          f"{invoice.issued_on} · {invoice.currency}")
    for item in invoice.items:
        print(f"     {item.quantity} x {item.description:<24} @ {item.unit_price:>8.2f}")
    print(f"     total: {invoice.total:.2f}  ({type(invoice.issued_on).__name__})")
    return invoice

if __name__ == "__main__":
    print(f"\nLedger: invoice extractor ({MODEL_ID}). Type 'exit' to quit.")
    print("Available:", ", ".join(sorted(p.name for p in SANDBOX.glob("*.txt"))))

    while True:
        user_input = input("\nInvoice > ")
        if user_input.lower() == "exit":
            break
        extract(user_input)
