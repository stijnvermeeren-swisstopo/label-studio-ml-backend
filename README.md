This repository is taken and adapted from [label-studio-ml-backend](https://github.com/HumanSignal/label-studio-ml-backend).

# What is the Label Studio ML backend?

The Label Studio ML backend is an SDK that lets you wrap your machine learning code and turn it into a web server.
The web server can be connected to a running [Label Studio](https://labelstud.io/) instance to automate labeling tasks.

If you just need to load static pre-annotated data into Label Studio, running an ML backend might be overkill for you.
Instead, you can [import preannotated data](https://labelstud.io/guide/predictions.html).

## Run the ML Backend

### 1. Installation

Download and install `label-studio-ml` from the repository:

```bash
git clone https://github.com/redur/label-studio-ml-backend.git
```

The code comes with two different ml-models that have their own respective endpoint. The directory structure for both models are the same. Information regarding the respective ML Models are found in their readmes located in the respective directories.

### 2. Prepare the services
The ML Models require the data available in their respective container. Therefore we need to ensure that the right directories are mounted. (Note: this should be deprecated once we move to S3 datastorage.).

The `stratigraphy-ml-backend` needs the original pdf files used for the stratigraphy algorithm. Create a directory containing the files and add it in the `docker-compose.yml` for the service `stratigraphy-ml-backend`.

The `text-extractor` service requires the png files of the extracted layers from the stratigraphy algorithm. Place the corresponding files in a directory and mount it in the `docker-compose.yml` for the `text-extractor` service.

### 3. Run the services
Run `docker-compose build` and `docker-compose up` to run both services.
Two endpoints will be created. The `stratigraphy-ml-backend` will listen on port `9090` and `text-extractor` will listen on port `9095`. You can now go to your label-studio front end and add the ML Backends in the UI. Note: You will have to find the IP adress of the docker containers first. You can find them in the logs. If you run them locally, it is your localhost.


## Extend / Adjust the Backend

### 1. File Structure
You can go to the `label_studio_ml/MODEL_NAME` directory and modify the code to implement your own inference logic.
The directory structure should look like this:

```
MODEL_NAME/
├── Dockerfile
├── model.py
├── _wsgi.py
├── README.md
└── requirements.txt
```

`Dockefile` is used to run the ML backend with Docker.
`model.py` is the main file where you can implement your own training and inference logic.
`_wsgi.py` is a helper file that is used to run the ML backend with Docker (you don't need to modify it)
`README.md` is a readme file with instructions on how to run the ML backend.
`requirements.txt` is a file with Python dependencies.


### 2. Implement prediction logic

In your model directory, locate the `model.py` file (for example, `my_ml_backend/model.py`).

The `model.py` file contains a class declaration inherited from `LabelStudioMLBase`. This class provides wrappers for
the API methods that are used by Label Studio to communicate with the ML backend. You can override the methods to
implement your own logic:

```python
def predict(self, tasks, context, **kwargs):
    """Make predictions for the tasks."""
    return predictions
```

The `predict` method is used to make predictions for the tasks. It uses the following:

- `tasks`: [Label Studio tasks in JSON format](https://labelstud.io/guide/task_format.html)
- `context`: [Label Studio context in JSON format](https://labelstud.io/guide/ml.html#Passing-data-to-ML-backend) - for
  interactive labeling scenario
- `predictions`: [Predictions array in JSON format](https://labelstud.io/guide/export.html#Raw-JSON-format-of-completed-tasks)

Once you implement the `predict` method, you can see predictions from the connected ML backend in Label Studio.

### 3. Implement training logic (optional)

You can also implement the `fit` method to train your model. The `fit` method is typically used to train the model on
the labeled data, although it can be used for any arbitrary operations that require data persistence (for example,
storing labeled data in database, saving model weights, keeping LLM prompts history, etc).
By default, the `fit` method is called at any data action in Label Studio, like creating a new task or updating
annotations. You can modify this behavior in Label Studio > Settings > Webhooks.

To implement the `fit` method, you need to override the `fit` method in your `model.py` file:

```python
def fit(self, event, data, **kwargs):
    """Train the model on the labeled data."""
    old_model = self.get('old_model')
    # write your logic to update the model
    self.set('new_model', new_model)
```

with

- `event`: event type can be `'ANNOTATION_CREATED'`, `'ANNOTATION_UPDATED'`, etc.
- `data` the payload received from the event (check more
  on [Webhook event reference](https://labelstud.io/guide/webhook_reference.html))

Additionally, there are two helper methods that you can use to store and retrieve data from the ML backend:

- `self.set(key, value)` - store data in the ML backend
- `self.get(key)` - retrieve data from the ML backend

Both methods can be used elsewhere in the ML backend code, for example, in the `predict` method to get the new model
weights.

#### Other methods and parameters

Other methods and parameters are available within the `LabelStudioMLBase` class:

- `self.label_config` - returns the [Label Studio labeling config](https://labelstud.io/guide/setup.html) as XML string.
- `self.parsed_label_config` - returns the [Label Studio labeling config](https://labelstud.io/guide/setup.html) as
  JSON.
- `self.model_version` - returns the current model version.
- `self.get_local_path(url, task_id)` - this helper function is used to download and cache an url that is typically stored in `task['data']`, 
and to return the local path to it. The URL can be: LS uploaded file, LS Local Storage, LS Cloud Storage or any other http(s) URL.      

#### Run without Docker

To run without docker (for example, for debugging purposes), you can use the following command: (make sure to install the dependencies beforehand).

```bash
label-studio-ml start my_ml_backend
```

#### Test your ML backend

Modify the `my_ml_backend/test_api.py` to ensure that your ML backend works as expected.

#### Modify the port

To modify the port, use the `-p` parameter:

```bash
label-studio-ml start my_ml_backend -p 9091
```

## Deploy your ML backend to GCP

Before you start:

1. Install [gcloud](https://cloud.google.com/sdk/docs/install)
2. Init billing for account if it's not [activated](https://console.cloud.google.com/project/_/billing/enable)
3. Init gcloud, type the following commands and login in browser:

```bash
gcloud auth login
```

4. Activate your Cloud Build API
5. Find your GCP project ID
6. (Optional) Add GCP_REGION with your default region to your ENV variables

To start deployment:

1. Create your own ML backend
2. Start deployment to GCP:

```bash
label-studio-ml deploy gcp {ml-backend-local-dir} \
--from={model-python-script} \
--gcp-project-id {gcp-project-id} \
--label-studio-host {https://app.heartex.com} \
--label-studio-api-key {YOUR-LABEL-STUDIO-API-KEY}
```

3. After label studio deploys the model - you will get model endpoint in console.

# Troubleshooting

## File not found
Make sure the right directories are mounted to your docker containers.

## Troubleshooting Pip Cache Reset in Docker Images

Sometimes, you want to reset the pip cache to ensure that the latest versions of the dependencies are installed. 
For example, Label Studio ML Backend library is used as
`label-studio-ml @ git+https://github.com/HumanSignal/label-studio-ml-backend.git` in requirements.txt. Let's assume that it
is updated, and you want to jump on the latest version in your docker image with the ML model. 

You can rebuild a docker image from scratch with the following command:

```bash
docker compose build --no-cache
```

# Development Roadmap
- Move files to S3
- Make it possible to upload files --> should be placed in a respective folder on S3