targetScope = 'resourceGroup'
param location string = resourceGroup().location
param webImage string
param apiImage string
@secure() param postgresAdminPassword string
var suffix=uniqueString(resourceGroup().id)
resource logs 'Microsoft.OperationalInsights/workspaces@2023-09-01'={name:'scratly-logs-${suffix}' location:location properties:{retentionInDays:30}}
resource insights 'Microsoft.Insights/components@2020-02-02'={name:'scratly-appi-${suffix}' location:location kind:'web' properties:{Application_Type:'web' WorkspaceResourceId:logs.id}}
resource storage 'Microsoft.Storage/storageAccounts@2023-05-01'={name:'scratlyfiles${suffix}' location:location sku:{name:'Standard_LRS'} kind:'StorageV2' properties:{allowBlobPublicAccess:false minimumTlsVersion:'TLS1_2'}}
resource pg 'Microsoft.DBforPostgreSQL/flexibleServers@2023-12-01-preview'={name:'scratly-pg-${suffix}' location:location sku:{name:'Standard_B1ms' tier:'Burstable'} properties:{administratorLogin:'scratlyadmin' administratorLoginPassword:postgresAdminPassword version:'16' storage:{storageSizeGB:32} backup:{backupRetentionDays:7}}}
resource env 'Microsoft.App/managedEnvironments@2024-03-01'={name:'scratly-env-${suffix}' location:location properties:{appLogsConfiguration:{destination:'log-analytics' logAnalyticsConfiguration:{customerId:logs.properties.customerId sharedKey:logs.listKeys().primarySharedKey}}}}
resource api 'Microsoft.App/containerApps@2024-03-01'={name:'scratly-api' location:location identity:{type:'SystemAssigned'} properties:{managedEnvironmentId:env.id configuration:{ingress:{external:true targetPort:8000} secrets:[{name:'db-password' value:postgresAdminPassword}]} template:{containers:[{name:'api' image:apiImage env:[{name:'AZURE_OPENAI_ENDPOINT' value:''},{name:'AZURE_OPENAI_ANALYZER_DEPLOYMENT' value:'analyzer'},{name:'AZURE_OPENAI_WRITER_DEPLOYMENT' value:'writer'},{name:'AZURE_OPENAI_SUMMARY_DEPLOYMENT' value:'summary'}]}] scale:{minReplicas:1 maxReplicas:5}}}}
resource web 'Microsoft.App/containerApps@2024-03-01'={name:'scratly-web' location:location identity:{type:'SystemAssigned'} properties:{managedEnvironmentId:env.id configuration:{ingress:{external:true targetPort:3000}} template:{containers:[{name:'web' image:webImage}] scale:{minReplicas:1 maxReplicas:3}}}}
resource blobRole 'Microsoft.Authorization/roleAssignments@2022-04-01'={name:guid(storage.id,api.id,'blob') scope:storage properties:{principalId:api.identity.principalId principalType:'ServicePrincipal' roleDefinitionId:subscriptionResourceId('Microsoft.Authorization/roleDefinitions','ba92f5b4-2d11-453d-a403-e96b0029c9fe')}}
