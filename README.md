# Azure Cost Exporter

On Azure we usually use the Cost Management portal to analyze costs, which is a separate dashboard and it only contains cost information. What if we would like to see the trends of both costs and the business metrics? Azure Cost Explorter enables this idea by exposing Azure cost data as Prometheus metrics so that developers can have them together with other observability metrics, in the same place.

## NOTICE

This project is **strongly** based on [azure-cost-exporter](https://github.com/opensourceelectrolux/azure-cost-exporter).
The main difference is that original project is able to scrape cost from several subscription in the same process while
the forked version is able to scrape costs from a single subscription. On the other hand, the forked version of the project
supports multiple authentication methods within Azure API (including ServicePrincial, ManagedIdentity, Azure CLI, Azure Powershell)
due to the usage of [DefaultAzureCredential](https://learn.microsoft.com/en-us/python/api/azure-identity/azure.identity.defaultazurecredential?view=azure-python)
python class.

Additionally, the forked version exports cost in USD and local currency relative to subscription ID.

## Sample Output

```
# HELP azure_daily_cost Daily cost of an Azure account
# TYPE azure_daily_cost gauge
azure_daily_cost{ChargeType="ActualCost",Currency="USD",EnvironmentName="dev",ProjectName="myproject",ResourceGroupName="<ResourceGroup>",ServiceName="Azure Bastion",Subscription="<Subscription ID>"} 3.5553768
azure_daily_cost{ChargeType="ActualCost",Currency="EUR",EnvironmentName="dev",ProjectName="myproject",ResourceGroupName="<ResourceGroup>",ServiceName="Azure Bastion",Subscription="<Subscription ID>"} 3.2016
azure_daily_cost{ChargeType="ActualCost",Currency="USD",EnvironmentName="dev",ProjectName="myproject",ResourceGroupName="<ResourceGroup>",ServiceName="Azure DNS",Subscription="<Subscription ID>"} 0.0147971447620323
azure_daily_cost{ChargeType="ActualCost",Currency="EUR",EnvironmentName="dev",ProjectName="myproject",ResourceGroupName="<ResourceGroup>",ServiceName="Azure DNS",Subscription="<Subscription ID>"} 0.0133247589032258
...
```

*ps: `Daily` is based a fixed 24h time window, from UTC 00:00 to UTC 24:00.
`EnvironmentName` and `ProjectName` are the custom labels that can be configured.
`ServiceName` is a label based on `group_by` configuration.*

## How Does This Work

Azure Cost Exporter calls Azure Cost Management API (`query.usage`) to fetch cost data.

## Register Application on Azure, Get Credentials

In order to invoke Azure API, the identity used to authenticate the application needs to have assigned the `Cost Management Reader` role.

Here are the steps of registering an application.

- Login to Azure portal (portal.azure.com).
- Visit `App registrations` page, and click the button `New registration`.
  - Specify a name.
  - Choose `Accounts in this organizational directory only (Single tenant)` as the account type.
- Visit `Subscriptions` page, choose the subscription that you would like to fetch cost data from.
  - Go to the `Access control (IAM)` page under the selected subscription.
  - Click `Add` - `Add role assignment`, under the `Role` tab, select `Cost Management Reader`, under the `Members` tag, assign access to `User, group, or service principal` and select the created application as the member, then review and assign the role.

Here are the steps of creating client credentials.

- Visit the application page via the `App registrations` portal or from the search textbox.
- Under the `Essentials` section, you will need the values of `Application (client) ID`, and `Directory (tenant) ID`.
- Go to `Certificates & secrets - Client secrets`, and click `New client secret`.
  - After clicking the `Add` button, remember to copy the client secret to a safe place because Azure only shows it once.

## Deployment

Modify the `exporter_config.yaml` file according to your needs file.
Configure the authentication method to be used, if using Service Principal, one of the following set
of [environment variables](https://learn.microsoft.com/en-us/python/api/azure-identity/azure.identity.environmentcredential?view=azure-python)
are needed.

### Docker

```
docker run --rm -v ./exporter_config.yaml:/app/exporter_config.yaml -p 9090:9090 ghcr.io/Wiston999/azure-cost-exporter:master
```

### Kubernetes

- Create Namespace
```
kubectl create ns finops
```

- Create Secret
```
kubectl create secret generic azure-cost-exporter \
    --namespace=finops \
    --from-literal=AZURE_TENANT_ID=<Tenant ID> \
    --from-literal=AZURE_CLIENT_ID=<SP Client ID> \
    --from-literal=AZURE_CLIENT_SECRET=<SP Client secret>
```

- Create ConfigMap
```
kubectl create configmap azure-cost-exporter-config --namespace finops --from-file=./exporter_config.yaml
```

- Create Deployment
```
kubectl create --namespace finops -f ./deployment/k8s/deployment.yaml
```
