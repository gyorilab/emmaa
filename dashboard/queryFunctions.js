// EMMAA rest API
var EMMAA_API = './query/submit'
var QUERY_STATUS_ID = 'query-status'

$(document).ready(function() {
  fillNamespaceOptions()
})

function postQuery(queryContainer) {
  console.log('function postQuery(queryContainer)')

  // Get user info
  userInfo = {
    name: 'joshua',
    slack_id: '123456abcdef',
    email: 'joshua@emmaa.com'
  }

  // Collect model query
  let querySel = collectQuery(queryContainer)
  if (querySel.length < 2) {
    queryNotify('Did not send query');
    return;
  }

  // Check if user wants to register query
  let reg = document.getElementById('register-query').checked

  let ajax_response = submitQuery({
    user: userInfo,
    models: querySel[0],
    query: querySel[1],
    register: reg
  }, null)

  console.log("ajax response from submission: ");
  console.log(ajax_response);
}

function collectQuery(queryContainer) {
  console.log('function collectQuery(queryContainer)')
  let dropdownSelections = queryContainer.getElementsByClassName('custom-select')

  result = []
  query = {};
  checkboxes = []

  // Get checked models
  for (box of document.getElementById('model-select').getElementsByTagName('input')) {
    console.log(box.name)
    if (!box.disabled && box.checked) {
      checkboxes.push(box.name)
    }
  }
  if (checkboxes.length == 0) {
    // Handle no boxes ticked
    alert('Must select at least one model!')
    return;
  };
  result.push(checkboxes);

  //  Collect dropdown selections
  for (selection of dropdownSelections) {
    selId = selection.id;
    // Use the IDs of the select tags as keys in the query json
    query[selId] = selection.options[selection.selectedIndex].value;
  }

  // Collect subject/object from forms
  query['subjectSelection'] = document.getElementById('subjectInput').value;
  query['objectSelection'] = document.getElementById('objectInput').value;
  result.push(query);

  return result;
}

function submitQuery(queryDict, test) {
  console.log('function submitQuery(queryDict)')
  console.log('Submitting data to query DB')
  console.log(queryDict)

  if (test) queryDict['test'] = true;

  // submit POST to emmaa user db
  queryNotify('Waiting for server response');
  $('#query-status-gif').show();
  let response = $.ajax({
    url: EMMAA_API,
    type: 'POST',
    dataType: 'json',
    contentType: 'application/json',
    data: JSON.stringify(queryDict),
    complete: function(xhr, statusText) {
      console.log('responseJSON')
      console.log(xhr.responseJSON)
      console.log(statusText)
      $('#query-status-gif').hide();
      switch (xhr.status) {
        case 200:
          console.log('200 response')
          queryNotify('Query resolved')
          populateQueryResults(xhr.responseJSON)
          break;
        case 400:
          console.log('400 response')
          queryNotify('Query failed: ' + statusText)
          break;
        case 401:
          console.log('401 response')
          queryNotify('Query failed: ' + statusText)
          break;
        case 404:
          console.log('404 response')
          queryNotify('Query failed: ' + statusText)
          break;
        case 500:
          console.log('500 response')
          queryNotify('Query failed: ' + statusText)
          break;
        default:
          console.log('Unhandled server response: ' + xhr.status)
          queryNotify('Query failed: ' + statusText)
      }
    }
  })
  return response;
}

function populateQueryResults(json) {
  console.log('function populateQueryResults(json)')
  console.log(json)
  let qrTable = document.getElementById('queryResults');
  clearTable(qrTable)
  for (model in json.result) {
    qrTable.appendChild(addToRow([model, json.result[model]]));
  }
}

function fillNamespaceOptions() {
  for (nsDD of document.getElementsByClassName('namespace-dropdown')) {
    console.log(nsDD)
    for (n_v of NAMESPACE_OPTIONS) {
      let optionTag = document.createElement('option');
      optionTag.value = n_v[1];
      optionTag.textContent = n_v[0];
      console.log(optionTag.textContent)
      nsDD.appendChild(optionTag);
    }
  }
}

function queryNotify(msg) {
  document.getElementById(QUERY_STATUS_ID).textContent = msg;
}
