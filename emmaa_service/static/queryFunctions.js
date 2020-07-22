// EMMAA rest API
let EMMAA_API = './query/submit';
// let QUERY_STATUS_ID = 'query-status';

function postQuery(queryContainer) {
  console.log('function postQuery(queryContainer)');

  // Collect model query
  let querySel = collectQuery(queryContainer);
  if (queryContainer.id == 'query-container') {
    var statusId = 'query-status';
    var tab = 'static';
    var reg = document.getElementById('register-query').checked;
  } else if (queryContainer.id == 'dynamic-container') {
    var statusId = 'dyn-query-status';
    var tab = 'dynamic';
    var reg = document.getElementById('register-dyn-query').checked;
  } else {
    var statusId = 'open-query-status';
    var tab = 'open';
    var reg = document.getElementById('register-open-query').checked;
  }
  if (querySel.length < 2) {
    queryNotify('Did not send query', statusId);
    return;
  }

  let ajax_response = submitQuery({
    models: querySel[0],
    query: querySel[1],
    register: reg
  }, tab, null);

  console.log("ajax response from submission: ");
  console.log(ajax_response);
}

function collectQuery(queryContainer) {
  console.log('function collectQuery(queryContainer)');
  console.log(queryContainer.id)
  let dropdownSelections = queryContainer.getElementsByClassName('custom-select');

  let result = [];
  let query = {};
  let models = [];

  // Get checked models
  if (queryContainer.id == 'query-container') {
    for (op of document.getElementById('model-select').children) {
      console.log(op.value);
      models.push(op.value);
    }
  } else  if (queryContainer.id == 'dynamic-container') {
    for (op of document.getElementById('dynamic-select').children) {
      console.log(op.value);
      models.push(op.value);
    };
  } else {
    for (op of document.getElementById('open-select').children) {
      console.log(op.value);
      models.push(op.value);
    };
  };
  if (models.length === 0) {
    // Handle no boxes ticked
    alert('Must select at least one model!');
    return;
  }
  result.push(models);

  //  Collect dropdown selections
  for (let selection of dropdownSelections) {
    let selId = selection.id;
    // Use the IDs of the select tags as keys in the query json
    query[selId] = selection.options[selection.selectedIndex].value;
  }

  // Collect subject/object/agent from forms
  if (queryContainer.id == 'query-container') {
    query['subjectSelection'] = document.getElementById('subjectInput').value;
    query['objectSelection'] = document.getElementById('objectInput').value;
    if (query['subjectSelection'] === '') {
      alert('Must provide a subject!');
      return;
    }
    if (query['objectSelection'] === '') {
      alert('Must provide an object!');
      return;      
    }
  } else if (queryContainer.id == 'dynamic-container') {
    query['agentSelection'] = document.getElementById('agentInput').value;
    if (query['agentSelection'] === '') {
      alert('Must provide an agent description!');
      return;
    } 
  } else {
    query['openAgentSelection'] = document.getElementById('openAgentInput').value;
    if (query['openAgentSelection'] === '') {
      alert('Must provide an agent description!');
      return;
    }
    if (query['signSelection'] === 'positive') {
      query['signSelection'] = 0;
    } else {
      query['signSelection'] = 1;
    }
    query['nsSelection'] = []
    for (op of document.getElementById('ns-select').children) {
      console.log(op.value);
      query['nsSelection'].push(op.value);
    }
  }
  result.push(query);
  return result;
}

function submitQuery(queryDict, tab, test) {
  console.log('function submitQuery(queryDict)');
  console.log('Submitting data to query DB');
  console.log(queryDict);
  console.log(tab)
  if (test) queryDict['test'] = true;

  // submit POST to emmaa user db 
  if (tab == 'static') {
    $('#query-status-gif').show();
    var statusId = 'query-status';
  } else if (tab == 'dynamic') {
    $('#dyn-query-status-gif').show();
    var statusId = 'dyn-query-status';
  } else {
    $('#open-query-status-gif').show();
    var statusId = 'open-query-status';
  }
  queryNotify('Waiting for server response', statusId);
  return $.ajax({
    url: EMMAA_API,
    type: 'POST',
    dataType: 'json',
    contentType: 'application/json',
    data: JSON.stringify(queryDict),
    complete: function(xhr, statusText) {
      console.log('responseJSON');
      console.log(xhr.responseJSON);
      console.log(statusText);
      $('#query-status-gif').hide();
      $('#dyn-query-status-gif').hide();
      switch (xhr.status) {
        case 200:
          console.log('200 response');
          queryNotify('Query resolved', statusId);
          if (xhr.responseJSON.redirectURL) {
            window.location.replace(xhr.responseJSON.redirectURL);
          }
          // populateQueryResults(xhr.responseJSON);
          break;
        case 400:
          console.log('400 response');
          queryNotify(xhr.responseText, statusId);
          break;
        case 401:
          console.log('401 response', statusId);
          let msg = 'Must be signed in to subscribe to queries';
          queryNotify(msg, statusId);
          if (queryDict.register) report_login_result(msg);
          login(
            (type, data) => {
              submitQuery(queryDict, test);
              handle_success(type, data);
            },
            (type, data) => {submitQuery(queryDict, test)}
          );

          break;
        case 404:
          console.log('404 response');
          queryNotify('Query failed: Not Found (404)', statusId);
          break;
        case 500:
          console.log('500 response');
          queryNotify('Query failed: Internal Server Error (500)', statusId);
          break;
        default:
          console.log(`Unhandled server response: ${xhr.status}`);
          queryNotify(`Query failed: ${xhr.status}`, statusId)
      }
    }
  });
}

function populateQueryResults(json) {
  console.log('function populateQueryResults(json)');
  console.log(json);
  let qrTable = document.getElementById('queryResults');
  clearTable(qrTable);
  for (let res of json.result) {
    let rowEl = addToRow([res['model'], res['model_type_name'], res['response']]);
    rowEl.children[1] = linkifyFromString(rowEl.children[2], rowEl.children[2].textContent);
    qrTable.appendChild(rowEl);
  }
}

function queryNotify(msg, statusId) {
  document.getElementById(statusId).textContent = msg;
}

function checkPattern() {
  let valuePatterns = ['always_value', 'sometime_value', 'eventual_value'];
  if (valuePatterns.includes(document.getElementById('patternSelection').value)) {
    document.getElementById('valueSelection').disabled=false;
  } else {
    document.getElementById('valueSelection').disabled=true;
    document.getElementById('valueSelection').value="";
  }
  console.log(document.getElementById('valueSelection').disabled)
  console.log(document.getElementById('valueSelection').value)
}