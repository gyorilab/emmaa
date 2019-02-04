/* awsServices.js - Organizes all functions relevant for AWS

Functions in this file are relevant to using AWS capabilites made available 
as javascript SDK. The functions are either wrapper/helper functions or 
direct implementations of the different services.

General Docs: https://docs.aws.amazon.com/AWSJavaScriptSDK/latest/

Docs for the S3 serivce:
https://docs.aws.amazon.com/AWSJavaScriptSDK/latest/AWS/S3.html

Docs for the cognito services:
https://docs.aws.amazon.com/AWSJavaScriptSDK/latest/AWS/CognitoIdentity.html
https://docs.aws.amazon.com/AWSJavaScriptSDK/latest/AWS/CognitoIdentityServiceProvider.html
https://docs.aws.amazon.com/AWSJavaScriptSDK/latest/AWS/CognitoIdentityCredentials.html

*/

// CONSTANTS AND IDs
var EMMMAA_BUCKET = 'emmaa';
var NOTIFY_STRING = 'status-notify';
var EMMAA_STATE_COOKIE_NAME = 'emmaaStateCookie=';
var EMMAA_ACCESSTOKEN_COOKIE_NAME = 'emmaaAccessCookie=';
var EMMAA_IDTOKEN_COOKIE_NAME = 'emmaaIdCookie=';
var STATE_VALUE = '' // State value to secure requests to cognito endpoints
var ACCESS_TOKEN_STRING = ''; // access token string
var ACCESS_TOKEN = {}; // access token
var ID_TOKEN_STRING = ''; // id token string
var ID_TOKEN = {}; // id token
var REFRESH_TOKEN = ''; // refresh token (typically not provided without providing username/password directly)
var APP_CLIENT_ID = '3ej6b95mbsu28e5nkcb6oa8fnp';
var AUTH_ENDPOINT_BASE_URL = 'https://emmaa.auth.us-east-1.amazoncognito.com/oauth2/authorize?';
var USER_SIGNED_IN = false;
var identityId = '' // 

// cognito parameters
var USER_POOL_ID = 'us-east-1_5sb1590b6'; // User pool ID; User info lives here
var IDENTITY_POOL_ID = 'us-east-1:76854655-a365-4e69-b080-0f8ca94a46fc'; // IdentityPool Id for "emmaa s3 test pool"
AWS.config.region = 'us-east-1' // Set region
AWS.config.credentials = new AWS.CognitoIdentityCredentials({
    IdentityPoolId: IDENTITY_POOL_ID,
});
var cogIdServiceProvider = new AWS.CognitoIdentityServiceProvider();

function _getNewStateValue() {
  let state = ''
  let numArray = window.crypto.getRandomValues(new Uint32Array(4))
  for (num of numArray) {
    state = state + window.btoa(num).replace(/=/g, '');
  }
  return state;
}

function checkLatestModelsUpdate() {
  //                   mode, tableBody, testResultTableBody, s3Interface, bucket, model, prefix, maxKeys, endsWith
  listObjectsInBucketUnAuthenticated('modelUpdate', null, null, new AWS.S3(), EMMMAA_BUCKET, 'models', 100, '.pkl')
}

function listObjectsInBucketUnAuthenticated(mode, tableBody, testResultTableBody, s3Interface, bucket, model, prefix, maxKeys, endsWith) {
  console.log('listObjectsInBucketUnAuthenticated(mode, tableBody, testResultTableBody, s3Interface, bucket, model, prefix, maxKeys, endsWith)')
  let _maxKeys = 1000
  if (maxKeys & maxKeys < _maxKeys) {
    _maxKeys = maxKeys;
  }
  let params = {
    Bucket: bucket,
    MaxKeys: _maxKeys,
    Prefix: prefix
  }
  s3Interface.makeUnauthenticatedRequest('listObjectsV2', params, function(err, data) {
    if (err) console.log(err, err.stack);
    else {
      // console.log('List of objects resolved from S3')
      // console.log(data)
      switch (mode) {
        // Update last time models were updated
        case 'modelUpdate':
          modelsLastUpdated(data.Contents, endsWith)
          break;
        // List tests for selected model on models page
        case 'listModelTests':
          // tableBody, testResultTableBody, keyMapArray, model, endsWith
          console.log('case "listModelTests"')
          listModelTests(tableBody, testResultTableBody, data.Contents, model, endsWith);
          break;
        // Default behaviour: just list key,value pairs in table
        default:
          let tableBodyTag = document.getElementById(tableBody);
          tableBodyTag.innerHTML = null;
          for (let i = 0; i < data.Contents.length; i++) {
            if (data.Contents[i].Key.endsWith(endsWith)) {
              let tableRow = document.createElement('tr');
              
              let modelColumn = document.createElement('td');

              let modelLink = document.createElement('a');
              modelLink.setAttribute('href', '#'); // LINK TO MODEL
              modelLink.textContent = data.Contents[i].Key.split('/')[1]
              modelColumn.appendChild(modelLink)
              tableRow.appendChild(modelColumn);

              let testColumn = document.createElement('td');
              testColumn.textContent = data.Contents[i].Key.split('/')[2].split('.')[0];
              let testJsonPromise = getPublicJson(bucket, data.Contents[i].Key);
              testJsonPromise.then(function(json){
                if (json[0].passed) {
                  testColumn.setAttribute('bgcolor', '00AA55;'); // Green if passed
                }
                else {
                  testColumn.setAttribute('bgcolor', 'DD4400;'); // Red if not
                }
              });
              tableRow.appendChild(testColumn);

              tableBodyTag.appendChild(tableRow);
            }
          }
      }
    }
  });
};

// Lists object in bucket 'bucket' with prefix 'prefix' and file ending in 'endsWith'
// in table 'tableBody'
function listObjectsInBucket(tableBody, s3Interface, bucket, prefix, maxKeys, endsWith) {
  console.log('function listObjectsInBucket(s3Interface, bucket, prefix, maxKeys, endsWith)')
  let _maxKeys = 1000
  if (maxKeys) {
    _maxKeys = maxKeys;
  }
  let params = {
    Bucket: bucket,
    MaxKeys: _maxKeys,
    Prefix: prefix
  }
  s3Interface.listObjectsV2(params, function(err, data) {
    if (err) console.log(err, err.stack);
    else {
      // console.log('List of objects resolved from S3')
      // console.log(data)
      // let tableBody = document.getElementById('listObjectsTableBody');
      tableBody.innerHTML = null;
      for (let i = 0; i < data.Contents.length; i++) {
        if (data.Contents[i].Key.endsWith(endsWith)) {
          let tableRow = document.createElement('tr');
          
          let modelColumn = document.createElement('td');

          let modelLink = document.createElement('a');
          modelLink.setAttribute('href', '#'); // LINK TO MODEL
          modelLink.textContent = data.Contents[i].Key.split('/')[1]
          modelColumn.appendChild(modelLink)
          tableRow.appendChild(modelColumn);

          let testColumn = document.createElement('td');
          testColumn.textContent = data.Contents[i].Key.split('/')[2].split('.')[0];
          let testJsonPromise = getPublicJson(bucket, data.Contents[i].Key);
          testJsonPromise.then(function(json){
            if (json[0].passed) {
              testColumn.setAttribute('bgcolor', '00AA55;'); // Green if passed
            }
            else {
              testColumn.setAttribute('bgcolor', 'DD4400;'); // Red if not
            }
          });
          tableRow.appendChild(testColumn);

          tableBody.appendChild(tableRow);
        }
      }
    }
  });
};

// FIXME: redirect should be variable: could be index.html or model.html
function getTokenFromAuthEndpoint(currentUrl) {
  console.log('function getTokenFromAuthEndpoint(currentUrl)')
  STATE_VALUE = _getNewStateValue();
  // console.log('current STATE_VALUE: ' + STATE_VALUE)
  _writeCookie(EMMAA_STATE_COOKIE_NAME, STATE_VALUE, 1)
  base_url = AUTH_ENDPOINT_BASE_URL;
  resp_type = 'response_type=token';
  client_id='client_id=' + APP_CLIENT_ID;
  redirect = 'redirect_uri=' + currentUrl;
  state = 'state=' + STATE_VALUE;
  cutom_scope = 'https://s3.console.aws.amazon.com/s3/buckets/emmaa/results.read'
  scope = 'scope=aws.cognito.signin.user.admin+openid+profile+' + cutom_scope;
  let get_url = base_url + resp_type + '&' + client_id + '&' + redirect + '&' + state + '&' + scope;
  console.log('get_url=' + get_url)
  window.location.replace(get_url) // Redirect
}

// Signing in using username/password, return JWTs
function signIn(uname, pwd) {
  console.log('Sign in button')
  cogIdServiceProvider.initiateAuth({
    'AuthFlow': 'USER_PASSWORD_AUTH', // What type of authentication to use
    'ClientId': APP_CLIENT_ID, // AppClientId for UserPool??
    
    AuthParameters: {
      'USERNAME': uname,
      'PASSWORD': pwd
      /* '<StringType>': ... */
    }
  }, function(err, data) {
    return responseResolve(err, data);
  });
}

function responseResolve(err, data) {
  if (err) {
    console.log('Error occured while trying to initiate auth:')
    console.log(err, err.stack)
    return err
  } else {
    console.log('Auth data:')
    console.log(data)
    tokenData = data.AuthenticationResult;
    verifyUser(tokenData.AccessToken, tokenData.IdToken);
    return tokenData;
  }
}

// CHECK SIGN IN
// this function should check if there is a session active and get the user pool tokens for that session
function checkSignIn() {
  console.log('function checkSignIn()')
  STATE_VALUE = _readCookie(EMMAA_STATE_COOKIE_NAME);
  let return_url = window.location.href;
  console.log('Return url: ' + return_url);
  url_dict = getDictFromUrl(return_url)[0];

  // No dict returned. Probably at first visit to page
  if (!url_dict) return;
  // console.log('returned url_dict')
  // console.log(url_dict)

  // State value does not match, do not proceed; Simple first layer security
  if (url_dict['state'] != STATE_VALUE) {
    console.log('State Value does not match');
    let outputNode = document.getElementById(NOTIFY_STRING)
    notifyUser(outputNode, 'State Value does not match');
    return;
  };

  // Check if token flow
  if (url_dict['access_token']) {
    console.log('token from authorization-endpoint')
    if (verifyUser(url_dict['access_token'], url_dict['id_token'])) {
      console.log('User verified')
    } else {
      console.log('User could not be verified...')
    }
  } else {
    console.log('No pattern match...')
    let outputNode = document.getElementById(NOTIFY_STRING)
    notifyUser(document.getElementById('status-notify'), 'Unable to retreive session/session expired. Please log in again.');
  }
}

// VERIFY USER 
function verifyUser(accessTokenString, idTokenString) {
  console.log('function verifyUser(accessTokenString, idTokenString)');
  cogIdServiceProvider.getUser({'AccessToken': accessTokenString}, function(err, data) {
    if (err) {
      let outputNode = document.getElementById(NOTIFY_STRING)
      notifyUser(outputNode, 'Could not verify user');
      return false;
    } else {
      // console.log('User meta data from cogIdServiceProvider.getUser()');
      // console.log(data);
      username = data.Username;
      let outputNode = document.getElementById(NOTIFY_STRING)
      notifyUser(outputNode, 'Hello ' + username);
      ACCESS_TOKEN_STRING = accessTokenString;
      _writeCookie(EMMAA_ACCESSTOKEN_COOKIE_NAME, ACCESS_TOKEN_STRING, 1);
      ID_TOKEN_STRING = idTokenString;
      _writeCookie(EMMAA_IDTOKEN_COOKIE_NAME, ID_TOKEN_STRING, 1);
      USER_SIGNED_IN = true
      addUserToIdentityCredentials(ID_TOKEN_STRING) // Add user to identity pool 
      return true;
    }
  })
}

// ADD USER TO THE CREDENTIALS LOGIN MAP
function addUserToIdentityCredentials(userIdToken) {
  console.log('Linking user to IdentityPool with ID userIdToken')
  AWS.config.credentials = new AWS.CognitoIdentityCredentials({
      IdentityPoolId: IDENTITY_POOL_ID,
      Logins: {
        // cognito-idp.<region>.amazonaws.com/<YOUR_USER_POOL_ID>
        'cognito-idp.us-east-1.amazonaws.com/us-east-1_5sb1590b6': userIdToken
      }
  });

  // Call to obtain credentials
  AWS.config.credentials.get(function(){

      // Credentials will be available when this function is called.
      var accessKeyId = AWS.config.credentials.accessKeyId;
      var secretAccessKey = AWS.config.credentials.secretAccessKey;
      var sessionToken = AWS.config.credentials.sessionToken;
  });

  // AWS.config.credentials.identityId should now be available
  console.log('Setting identityId for logged in user')
  identityId = AWS.config.credentials.identityId;
}

// Can be used when something is public on S3
function getPublicJson(bucket, key) {
  // For production: get list of results and select based on some criteria
  base_url = 'https://s3.amazonaws.com'
  pathString = '/' + bucket + '/' + key;
  url = base_url +  pathString.replace(/\/\//g, '/'); // Avoid double slashes;
  // console.log('getting json from ' + url);
  return grabJSON(url);
}

// When and object needs credentials to be read from S3
function readFromS3(bucket, key) {
  s3InterfaceOptions = {
    credentials: AWS.config.credentials
  }
  console.log('New s3 interface object using the following AWS.config.credentials:');
  console.log(AWS.config.credentials);
  var s3Interface = new AWS.S3(s3InterfaceOptions);
  var params = {
    Bucket: bucket,
    Key: key
    // Bucket: 'emmaa-test',
    // Key: 'test-results-public/test_json_on_S3.json',
  }

  // Documentation for s3.getObject():
  // https://docs.aws.amazon.com/AWSJavaScriptSDK/latest/AWS/S3.html#getObject-property
  s3Interface.getObject(params, function(err, data){
    if (err) {
      console.log(err);
      return;
    }
    else {
      console.log('S3 getOjbect resolved successfully');
      console.log(data);
      let s3ObjectJSON = data.Body;
      return s3ObjectJSON;
    }
  });
}
