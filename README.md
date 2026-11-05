# RouteWise AI

**Agentic AI-powered Indian travel planning platform powered by IBM
Granite and IBM watsonx.ai.**

Built for the **IBM SkillsBuild University Education Internship**.

RouteWise AI brings destination discovery, route information, budget
estimation, weather context, itinerary generation and itinerary
replanning into one Streamlit application.

------------------------------------------------------------------------

## Table of contents

-   [Project overview](#project-overview)
-   [Key features](#key-features)
-   [How it works](#how-it-works)
-   [Technology stack](#technology-stack)
-   [Project structure](#project-structure)
-   [Requirements](#requirements)
-   [Run locally on Windows](#run-locally-on-windows)
-   [Configure IBM watsonx.ai](#configure-ibm-watsonxai)
-   [Upload the project to GitHub](#upload-the-project-to-github)
-   [Deploy on Streamlit Community
    Cloud](#deploy-on-streamlit-community-cloud)
-   [Configure Streamlit Secrets](#configure-streamlit-secrets)
-   [Verify the deployed application](#verify-the-deployed-application)
-   [Update the deployed application](#update-the-deployed-application)
-   [Troubleshooting](#troubleshooting)
-   [Security](#security)
-   [Known limitations](#known-limitations)
-   [Responsible AI](#responsible-ai)
-   [License](#license)

------------------------------------------------------------------------

## Project overview

Trip planning often requires travellers to switch between different
services for destination research, route information, cost estimation,
weather forecasts and itinerary preparation. RouteWise AI aims to make
this process easier through a single travel-planning interface.

The application uses IBM Granite through IBM watsonx.ai for
language-based reasoning. Python handles application logic, validation
and deterministic calculations. External services provide weather and
route-related information where available.

RouteWise AI is a planning assistant. It does not make bookings or
payments.

## Key features

  -----------------------------------------------------------------------
  Feature                             Description
  ----------------------------------- -----------------------------------
  Multi-agent planning workflow       Specialized agents handle different
                                      parts of a travel request through a
                                      central orchestrator.

  Destination intelligence            Provides destination suggestions
                                      and relevant travel information for
                                      Indian destinations.

  Day-by-day itinerary                Produces structured travel plans
                                      with activities and estimated
                                      costs.

  Budget estimation                   Calculates estimated travel costs
                                      and compares them with the supplied
                                      budget.

  Weather information                 Uses Open-Meteo for available
                                      forecast information.

  Route information                   Uses OpenStreetMap-based geocoding
                                      and OSRM routing where available.

  Dynamic itinerary replanning        Proposes changes to affected
                                      itinerary days when a disruption is
                                      reported. User approval is required
                                      before applying a proposed change.

  Interactive map                     Displays destination and route
                                      information on a map.

  Input and output validation         Validates user inputs and checks
                                      structured model responses before
                                      using them.
  -----------------------------------------------------------------------

## How it works

A travel request is validated and passed to the application
orchestrator. The orchestrator coordinates the relevant specialized
agents. The agents use IBM Granite for language-based tasks and Python
or external services for deterministic calculations and retrieved
information.

The application includes these agents:

  -----------------------------------------------------------------------
  Agent                               Responsibility
  ----------------------------------- -----------------------------------
  `PreferenceAgent`                   Interprets travel preferences and
                                      priorities.

  `DestinationAgent`                  Assesses destination suitability
                                      and provides destination
                                      information.

  `RouteAgent`                        Retrieves or estimates route
                                      distance and transport information.

  `BudgetAgent`                       Calculates estimated costs and
                                      provides budget-related guidance.

  `WeatherAgent`                      Uses available weather information
                                      and provides a travel-oriented
                                      assessment.

  `ItineraryAgent`                    Generates and validates structured
                                      day-by-day itinerary content.

  `ReplanningAgent`                   Proposes itinerary changes when the
                                      user reports a disruption.
  -----------------------------------------------------------------------

The agents are application components coordinated by an orchestrator;
they are not seven separately hosted foundation models.

## Technology stack

  -----------------------------------------------------------------------
  Layer                               Technology
  ----------------------------------- -----------------------------------
  User interface                      Streamlit

  Language model                      IBM Granite
                                      (`ibm/granite-4-h-small`, subject
                                      to account and region availability)

  Model platform and SDK              IBM watsonx.ai, `ibm-watsonx-ai`

  Programming language                Python

  Data validation                     Pydantic

  Data processing                     Pandas

  Visualization                       Plotly

  Interactive maps                    Folium and Streamlit-Folium

  HTTP requests                       Requests

  Weather data                        Open-Meteo

  Geocoding and routing               OpenStreetMap Nominatim and OSRM

  Local configuration                 `python-dotenv`
  -----------------------------------------------------------------------

## Project structure

``` text
RouteWise_AI/
│
├── app.py
├── config.py
├── requirements.txt
├── runtime.txt
├── README.md
├── LICENSE
├── .gitignore
│
├── agents/
│   ├── orchestrator.py
│   ├── preference_agent.py
│   ├── destination_agent.py
│   ├── route_agent.py
│   ├── budget_agent.py
│   ├── weather_agent.py
│   ├── itinerary_agent.py
│   └── replanning_agent.py
│
├── services/
│   ├── watsonx_service.py
│   ├── weather_service.py
│   ├── maps_service.py
│   ├── model_discovery.py
│   └── destination_service.py
│
├── components/
│   ├── navigation.py
│   ├── itinerary_view.py
│   ├── budget_view.py
│   ├── map_view.py
│   └── destination_cards.py
│
├── models/
│   ├── travel_request.py
│   └── itinerary.py
│
├── utils/
│   ├── validation.py
│   ├── calculations.py
│   └── security.py
│
├── tests/
│
└── .streamlit/
    └── config.toml
```

`app.py` is the Streamlit application entry point. `requirements.txt`
contains the Python dependencies. `runtime.txt` specifies Python 3.11
for supported deployment environments.

## Requirements

-   Python 3.11
-   `pip`
-   An IBM Cloud account with access to IBM watsonx.ai and a watsonx.ai
    project
-   An IBM Cloud API key and the watsonx.ai project ID for live Granite
    inference
-   Git and a GitHub account for source-code hosting
-   A Streamlit Community Cloud account for cloud deployment

The IBM Granite model must be available to your IBM watsonx.ai account
in the selected region. Check model availability and the correct
endpoint in your IBM account.

## Run locally on Windows

### 1. Extract the project

Extract the project ZIP. Open the extracted `RouteWise_AI` folder in
Visual Studio Code or a terminal.

Make sure `app.py` and `requirements.txt` are directly inside the folder
you open.

### 2. Create a virtual environment

Open PowerShell in the project folder and run:

``` powershell
py -3.11 -m venv .venv
```

Activate it:

``` powershell
.\.venv\Scripts\Activate.ps1
```

If PowerShell blocks activation, you can use Command Prompt instead:

``` bat
.venv\Scripts\activate.bat
```

### 3. Install dependencies

``` powershell
python -m pip install --upgrade pip
pip install -r requirements.txt
```

### 4. Create your local `.env` file

Create a file named `.env` in the same folder as `app.py`. Add your IBM
configuration as shown in [Configure IBM
watsonx.ai](#configure-ibm-watsonxai).

Do not commit this file to GitHub. The repository's `.gitignore`
excludes `.env`.

### 5. Start the application

``` powershell
streamlit run app.py
```

Streamlit will show a local URL, usually `http://localhost:8501`.

## Configure IBM watsonx.ai

The application reads configuration from environment variables and
Streamlit Secrets. For local development, use a `.env` file in the
project root.

Example `.env` file:

``` dotenv
WATSONX_API_KEY=your_ibm_cloud_api_key
WATSONX_PROJECT_ID=your_watsonx_project_id
WATSONX_URL=https://us-south.ml.cloud.ibm.com
WATSONX_MODEL_ID=ibm/granite-4-h-small

MAX_NEW_TOKENS=1200
MODEL_TEMPERATURE=0.3
REQUEST_TIMEOUT=60
```

Replace the example API key and project ID with your own values. Use the
endpoint corresponding to your IBM watsonx.ai region. The model ID shown
is the project's configured default; confirm that it is available to
your account and region.

### Where to find the values

  -----------------------------------------------------------------------
  Setting                             Where to find it
  ----------------------------------- -----------------------------------
  `WATSONX_API_KEY`                   IBM Cloud → Manage → Access (IAM) →
                                      API keys

  `WATSONX_PROJECT_ID`                Open your watsonx.ai project and
                                      find its project ID in project
                                      management details

  `WATSONX_URL`                       Use the watsonx.ai service endpoint
                                      for your IBM Cloud region

  `WATSONX_MODEL_ID`                  Use a Granite model ID available to
                                      your account and region

  `MAX_NEW_TOKENS`                    Optional inference output limit;
                                      default is `1200`

  `MODEL_TEMPERATURE`                 Optional generation temperature;
                                      default is `0.3`

  `REQUEST_TIMEOUT`                   Optional request timeout in
                                      seconds; default is `60`
  -----------------------------------------------------------------------

The application also has default values for the model ID, endpoint, and
inference settings in `config.py`. Live Granite inference requires a
valid API key and project ID.

## Upload the project to GitHub

These instructions use GitHub Desktop on Windows.

### 1. Create a GitHub repository

1.  Sign in to [GitHub](https://github.com/).
2.  Open [Create a new repository](https://github.com/new).
3.  Enter a repository name, for example `RouteWise-AI`.
4.  Add a short description, such as
    `Agentic AI-powered Indian travel planning platform using IBM Granite and Streamlit`.
5.  Choose Public or Private.
6.  Do not initialize the repository with another README, `.gitignore`,
    or license because these files are already included in this project.
7.  Click **Create repository**.

### 2. Install GitHub Desktop

Download and install [GitHub Desktop](https://desktop.github.com/), then
sign in with the same GitHub account.

### 3. Add the local project

1.  Open GitHub Desktop.
2.  Choose **File → Add Local Repository** if the project is already a
    Git repository.
3.  If it is not yet a Git repository, choose **File → New Repository**
    and set the local path to the extracted `RouteWise_AI` project
    folder.
4.  Use `RouteWise-AI` as the repository name if desired.
5.  Create the repository.

### 4. Check files before publishing

Before publishing, inspect the changed-files list in GitHub Desktop.

Confirm that: - `app.py`, `config.py`, `requirements.txt`,
`runtime.txt`, `README.md`, and the application folders are included. -
`.env` is not included. - `.streamlit/secrets.toml` is not included. -
No API keys, passwords, tokens, or other private credentials appear in
files being uploaded.

The `.gitignore` file excludes `.env` and `.streamlit/secrets.toml`, but
you must still inspect the files before publishing. `.gitignore` does
not remove a secret that was already committed previously.

### 5. Publish the repository

1.  Enter a commit message, for example
    `Initial RouteWise AI project upload`.
2.  Click **Commit to main**.
3.  Click **Publish repository**.
4.  Select whether the GitHub repository should be public or private.
5.  Confirm publishing.

Open the repository on GitHub and verify that `app.py` and
`requirements.txt` are visible at the repository root. The repository
root should not contain an extra nested `RouteWise_AI/RouteWise_AI/`
directory.

## Deploy on Streamlit Community Cloud

### 1. Open Streamlit Community Cloud

Go to <https://share.streamlit.io/> and sign in using GitHub.

Authorize access to the repository you want to deploy. If the repository
is private, grant Streamlit the required private-repository access.

### 2. Create the application

1.  Click **Create app**.

2.  Select the GitHub repository containing RouteWise AI.

3.  Select the `main` branch (or the branch where you uploaded the
    project).

4.  Set **Main file path** to:

    ``` text
    app.py
    ```

5.  Choose an available app subdomain if prompted.

6.  Open **Advanced settings** and select Python 3.11 if the option is
    available.

7.  Add the Streamlit Secrets described in the next section.

8.  Save and deploy.

Streamlit Community Cloud installs packages from `requirements.txt` and
runs the selected entry-point file.

Official deployment guide:\
https://docs.streamlit.io/deploy/streamlit-community-cloud/deploy-your-app/deploy

## Configure Streamlit Secrets

Do not upload your local `.env` file to GitHub. For the deployed
application, configure credentials in the Streamlit app's **Settings →
Secrets** section.

Paste this TOML configuration into the Secrets editor and replace the
two placeholders with your own credentials:

``` toml
WATSONX_API_KEY = "your_ibm_cloud_api_key"
WATSONX_PROJECT_ID = "your_watsonx_project_id"
WATSONX_URL = "https://us-south.ml.cloud.ibm.com"
WATSONX_MODEL_ID = "ibm/granite-4-h-small"

MAX_NEW_TOKENS = "1200"
MODEL_TEMPERATURE = "0.3"
REQUEST_TIMEOUT = "60"
```

Keep the quotation marks around the values. Use the endpoint for your
IBM region and a model ID available to your project.

After saving the Secrets, restart or redeploy the app if required. The
project's `config.py` reads from Streamlit Secrets, so a separate `.env`
file is not required on Streamlit Community Cloud.

Official secrets guide:\
https://docs.streamlit.io/deploy/streamlit-community-cloud/deploy-your-app/secrets-management

## Verify the deployed application

After deployment completes, open the Streamlit app URL and check the
following:

1.  The application opens without import or dependency errors.
2.  The Settings page shows that the required IBM configuration is
    present without displaying secret values.
3.  Use the application's **Test IBM Granite Connection** control to
    test live model inference.
4.  Submit a sample travel request and verify that the itinerary is
    generated.
5.  Check destination, route, budget, weather and map sections.
6.  Test itinerary replanning and confirm that proposed changes require
    user approval.
7.  Review Streamlit deployment logs if an error occurs.

A successful credentials check is not the same as verifying every agent
workflow. Confirm that an actual itinerary request completes with
Granite and inspect the application status or logs if a template
fallback is displayed.

## Update the deployed application

When you change the local project:

1.  Open the project in your code editor.
2.  Make and test your changes locally.
3.  Open GitHub Desktop.
4.  Review the modified files.
5.  Enter a meaningful commit message.
6.  Click **Commit to main**.
7.  Click **Push origin**.

Streamlit Community Cloud normally detects the new GitHub commit and
redeploys the application automatically.

## Troubleshooting

  -----------------------------------------------------------------------
  Problem                             What to check
  ----------------------------------- -----------------------------------
  `ModuleNotFoundError` during        Confirm the required package is
  deployment                          listed in `requirements.txt`, then
                                      commit and push the change.

  Python version or package           Check `runtime.txt` and the package
  installation error                  compatibility shown in the build
                                      logs.

  IBM authentication error            Verify `WATSONX_API_KEY` in
                                      Streamlit Secrets and create a
                                      replacement key if the old one was
                                      revoked.

  IBM project not found               Verify `WATSONX_PROJECT_ID` and
                                      confirm that the project belongs to
                                      the IBM account and region being
                                      used.

  Model unavailable                   Confirm model availability and
                                      access for the configured region
                                      and project.

  Incorrect endpoint or region        Verify `WATSONX_URL` against the
                                      IBM watsonx.ai service endpoint for
                                      your project.

  Template or fallback itinerary      Inspect the app logs and Granite
  appears                             response. A configured key alone
                                      does not prove successful model
                                      inference or valid structured
                                      output.

  Map or route data does not load     Check external service
                                      availability, rate limits and the
                                      deployment logs.

  Secrets appear missing              Check the Streamlit app's Secrets
                                      settings for TOML syntax, key names
                                      and saved values.
  -----------------------------------------------------------------------

When requesting help, share the relevant error message with API keys,
project secrets, tokens and personal information removed.

## Security

-   Never commit `.env`, `.streamlit/secrets.toml`, API keys, passwords
    or access tokens.
-   Keep the repository's `.gitignore` file in place.
-   Configure deployment credentials using Streamlit Secrets.
-   Do not paste credentials into source code, README files,
    screenshots, issue reports or public messages.
-   If a real API key is accidentally published, revoke it in IBM Cloud
    IAM and create a replacement. Removing it in a later commit does not
    erase it from Git history.
-   Do not log or display secret values.

## Known limitations

-   **Model access:** IBM Granite model availability depends on the IBM
    account, project and region.
-   **Forecast range:** Weather forecast coverage depends on the
    forecast service's available range and the requested travel dates.
-   **External services:** Open-Meteo, OSRM and OpenStreetMap services
    may be rate-limited or temporarily unavailable.
-   **Route estimates:** Route results depend on the available routing
    data. Some transport distances may be approximations.
-   **Destination coverage:** The curated destination information is
    focused on India and may not cover every location.
-   **Costs:** Budget and activity costs are estimates, not confirmed
    supplier prices.
-   **Bookings:** The application provides planning assistance and does
    not make actual travel reservations or payments.
-   **Model output:** Granite responses may require validation. If a
    response is incomplete or cannot be parsed, the application may use
    its configured fallback behavior.

## Responsible AI

-   Costs and budget calculations are presented as estimates.
-   The application validates structured model output before using it.
-   Template or fallback itinerary content should be distinguished from
    a successfully generated AI itinerary.
-   Users should verify important travel, weather, route and safety
    information with authoritative sources before travelling.
-   Replanning proposals require user approval before they are applied.
-   The application does not automatically make purchases or
    reservations.

## License

This project is distributed under the MIT License. See
[LICENSE](LICENSE) for details.

------------------------------------------------------------------------

**RouteWise AI --- Agentic AI-powered Indian Travel Planning**\
*IBM SkillsBuild University Education Internship Project*
