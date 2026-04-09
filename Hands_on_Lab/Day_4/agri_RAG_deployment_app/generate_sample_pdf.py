from reportlab.lib.pagesizes import letter
from reportlab.pdfgen import canvas

def create_pdf(filename):
    c = canvas.Canvas(filename, pagesize=letter)
    width, height = letter
    
    c.setFont("Helvetica-Bold", 16)
    c.drawString(100, height - 100, "Official AgroRAG Knowledge Base - Vol 1")
    
    c.setFont("Helvetica-Bold", 14)
    c.drawString(100, height - 140, "Topic: Tomato Disease Management")
    c.setFont("Helvetica", 12)
    c.drawString(100, height - 160, "Early Blight (Alternaria solani) often starts with small black spots on older leaves.")
    c.drawString(100, height - 175, "Treatment: Apply chlorothalonil or copper-based fungicides every 7-10 days.")
    c.drawString(100, height - 190, "Prevention: Ensure 24-inch spacing between plants for airflow.")
    
    c.setFont("Helvetica-Bold", 14)
    c.drawString(100, height - 230, "Topic: Soil Health for Wheat")
    c.setFont("Helvetica", 12)
    c.drawString(100, height - 250, "Wheat thrives best in well-drained loamy soil with a pH between 6.0 and 7.0.")
    c.drawString(100, height - 265, "If pH is below 5.5, apply lime (calcium carbonate) to neutralize acidity.")
    
    c.drawString(100, height - 300, "Document ID: AGRI-2024-001")
    c.showPage()
    c.save()

if __name__ == "__main__":
    create_pdf("agri_sample_docs.pdf")
    print("PDF generated successfully.")
