# docs-fill
A Python application using **FastAPI** to dynamically generate documents by filling out DOCX templates and converting them to PDF. It provides a simple, intuitive web interface and API endpoints for document generation and download.

### Initial Setup

1. **Clone the repository**: Clone this repository using `git clone`.
2. **Create Virtual Env**: Create a Python Virtual Env `venv` to download the required dependencies and libraries.
3. **Download Dependencies**: Download the required dependencies into the Virtual Env `venv` using `uv`.

```shell
git clone https://github.com/grisha765/docs-fill.git
cd docs-fill
python -m venv .venv
.venv/bin/python -m pip install uv
.venv/bin/python -m uv sync
```

### Deployment

- Run the application:
    ```bash
    PORT="8000" RELOAD="True" uv run main.py
    ```

#### Container

- Pull the container:
    ```bash
    podman pull ghcr.io/grisha765/docs-fill:latest
    ```

- Deploy using Podman:
    ```bash
    podman run -d \
    --name docs-fill \
    -v /path/to/docx_templates:/app/docx_templates:z \
    --p 8000:8000 \
    -e PORT="8000" \
    ghcr.io/grisha765/docs-fill:latest
    ```

#### Proxy on nginx

- Create a file `/etc/nginx/sites-enabled/example.com` with the lines:
    ```nginx
    server {
        listen 80 default;
        server_name example.com;
     
        location / {
            proxy_pass http://127.0.0.1:8000/;
            proxy_set_header Host $http_host;
            proxy_set_header X-Real-IP $remote_addr;
            proxy_set_header X-Forwarded-For $proxy_add_x_forwarded_for;
        }
    }
    ```

### Usage

- Open your browser and navigate to http://localhost:8000

#### API Endpoints

- Generate and download a document (using form data):
    ```bash
    curl -X POST http://localhost:8000/generate \
    -F "tpl=template.docx" \
    -F "field_name=value" \
    -F "fmt=pdf" --output output.pdf
    ```

Replace `template.docx` and `field_name=value` with your template and field data.

### Preparing Document Templates

#### How to Stack Documents:

- Place your DOCX template files and optional YAML metadata files in the `docx_templates` folder of the repository.
- YAML metadata files are used to define custom labels, input types, and choices for fields in the web interface.
- Ensure the YAML file has the **exact same filename** (excluding the extension) as the DOCX template file.

**Example structure**:

```
docx_templates/
├── agreement.docx
└── agreement.yaml
```

#### Example DOCX Document `agreement.docx`:

- Create a DOCX file using placeholders (Jinja-style) as follows:
    ```docx
    Agreement № {{agreement_number}}

    This Agreement is made on {{date}} between {{company_name}} (the "Company") and {{client_name}} (the "Client").

    - Agreement Amount: {{amount}}
    - Effective Date: {{effective_date}}
    - Payment Terms: {{payment_terms}}

    Signed by:
    {{company_representative}}
    ```

#### Corresponding YAML Metadata File `agreement.yaml`:

- Provide detailed field descriptions, input types, and choices for fields:
    ```yaml
    agreement_number:
      label: "Agreement Number"
      type: "string"

    date:
      label: "Agreement Date"
      type: "date"

    company_name:
      label: "Company Name"
      type: "string"

    client_name:
      label: "Client Name"
      type: "string"

    amount:
      label: "Agreement Amount (RUB)"
      type: "float"

    effective_date:
      label: "Effective Date"
      type: "date"

    payment_terms:
      label: "Payment Terms"
      type: "choice"
      choices:
        - "Net 30"
        - "Net 60"
        - "Net 90"
        - "Prepaid"

    company_representative:
      label: "Company Representative"
      type: "string"
    ```

This metadata will automatically generate appropriate form fields in the web interface, enhancing usability.

### Features

- Dynamic DOCX template rendering using form inputs.
- Automatic conversion from DOCX to PDF.
- Web interface for convenient document generation.
- API endpoints for automated or scripted document processing.
- Template metadata and form generation via YAML.
