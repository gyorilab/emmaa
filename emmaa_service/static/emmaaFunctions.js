/* emmaaFunctions.js - main javascript functions for the ASKE emmaa project

This file contains helper functions and project specific functions that does 
the client side work of exposing cancer network models for the end users

*/

const FORMATTED_MODEL_NAMES = {'pysb': 'PySB',
                         'pybel': 'PyBEL',
                         'signed_graph': 'Signed Graph',
                         'unsigned_graph': 'Unsigned Graph'}

function setModel(ddSelect, model) {
  // Sets the selected option
  // let ddSelect = document.getElementById('modelSelectDD');
  for (child of ddSelect.children) {
    if (model === child.value) {
      child.selected = 'selected';
      break;
    }
  }
}

function modelRedirect(ddSelect, current_model) {

  // Get selected option
  let newModel = '';
  for (child of ddSelect.children) {
    if (child.selected) {
      newModel = child.value;
      break;
    }
  }

  let loc = window.location.href;
  // remove current date and test corpus
  if (loc.includes('date')) {
    date = new URL(loc).searchParams.get('date');
    loc = loc.replace(`date=${date}`, '')
  }
  if (loc.includes('test_corpus')) {
    test_corpus = new URL(loc).searchParams.get('test_corpus');
    loc = loc.replace(`test_corpus=${test_corpus}`, '')
  }  
  if (loc.includes('tab')) {
    tab = new URL(loc).searchParams.get('tab');
    loc = loc.replace(`tab=${tab}`, 'tab=model')
  }  
  // redirect url:
  let redirect = loc.replace(current_model, newModel);
  if (redirect.endsWith('&')) {
    redirect = redirect.substr(0, redirect.length - 1);
  }
  console.log(redirect);
  window.location.replace(redirect);
}


function redirectToPast(x) { 
  let new_date = x.x;
  let static_date = new Date('2019-09-30');
  if (new_date >= static_date) {
    let year = new_date.getFullYear();
    let month = (1 + new_date.getMonth()).toString();
    month = month.length > 1 ? month : '0' + month;
    let day = new_date.getDate().toString();
    day = day.length > 1 ? day : '0' + day;
    let new_date_str = year + '-' + month + '-' + day;
    console.log(new_date_str)
    redirectToDate(new_date_str)
  } else {
    alert("Sorry, you cannot see the data before 2019-09-30")
  };
}

function redirectToDate(new_date_str) {
  let loc = window.location.href;
  let current_date = new URL(loc).searchParams.get('date');
  let redirect = '';
  if (current_date) {
    redirect = loc.replace(current_date, new_date_str)
  } else {
    if (loc.includes('?')) {
      // There are already other query paramters, append
      redirect = loc.concat(`&date=${new_date_str}`)
    } else {
      // This is only query paramter, add
      redirect = loc.concat(`?date=${new_date_str}`)
    }
  }

  location.replace(redirect);
}


function testRedirect(ddSelect) {
  for (child of ddSelect.children) {
    if (child.selected) {
      newTest = child.value;
      break;
    }
  }

  // remove date if it is in the url
  let loc = window.location.href
  if (loc.includes('date')) {
    date = new URL(loc).searchParams.get('date');
    loc = loc.replace(`date=${date}`, '')
  }
  // replace or add test corpus
  if (loc.includes('test_corpus')) {
    currentTest = new URL(loc).searchParams.get('test_corpus');
    loc = loc.replace(`test_corpus=${currentTest}`, `test_corpus=${newTest}`)
  } else {
    loc = loc.concat(`&test_corpus=${newTest}`)
  }
  console.log(loc)
  // redirect url:
  currentTab = new URL(loc).searchParams.get('tab')
  let redirectTab = loc.replace(`tab=${currentTab}`, 'tab=tests')
  location.replace(redirectTab);
}


function redirectOneStep(value, isQuery) {
  let loc = window.location.href;
  if (isQuery) {
    let currentOrder = new URL(loc).searchParams.get('order');
    var redirect = '';
    if (currentOrder) {
      redirect = loc.replace(`order=${currentOrder}`, `order=${value}`)
    } else {
      // Default if no order in query string
      redirect = loc.concat('&order=1')
    }
  } else {
    let currentDate = new URL(loc).searchParams.get('date')
    var redirect = loc.replace(`date=${currentDate}`, `date=${value}`)
  };
  location.replace(redirect);
}


function redirectOneArgument(newValue, param) {
  let loc = window.location.href;
  let currentValue = new URL(loc).searchParams.get(param);
  var redirect = loc.replace(`${param}=${currentValue}`, `${param}=${newValue}`)
  location.replace(redirect);
}


function redirectSelection(ddSelect, param) {
  // Get selected option
  let newValue = ''
  for (child of ddSelect.children) {
    if (child.selected) {
      newValue = child.value
      break;
    }
  }
  console.log(newValue)
  redirectOneArgument(newValue, param);
}


function clearTables(arrayOfTableBodies) {
  for (let tableBody of arrayOfTableBodies) {
    clearTable(tableBody)
  }
}

function clearTable(tableBody) {
  tableBody.innerHTML = null;
}

// Creates a new table row given an array of values
function addToRow(col_values) {
  let tableRow = document.createElement('tr');

  for (let col of col_values) {
    let column = document.createElement('td');
    column.textContent = col;
    tableRow.appendChild(column);
  }

  return tableRow;
}

// Creates a new table row by merging the columns
function addMergedRow(value, num_cols) {
  let tableRow = document.createElement('tr');
  let column = document.createElement('td')
  column.colSpan = num_cols
  column.innerHTML = value.bold()
  column.style.textAlign = "center"
  tableRow.appendChild(column);
  return tableRow;
}

function generatePassFail(rowEl, cols) {
  // See more at:
  // https://fontawesome.com/icons?d=gallery
  // Pass: <i class="fas fa-check"></i>
  // Fail: <i class="fas fa-times"></i>
  for (col of cols) {
    let string = rowEl.children[col].textContent;
    let itag = document.createElement('i');
    if (string.toLowerCase() === 'pass') {
      itag.className = 'fas fa-check';
      rowEl.children[col].innerHTML = null;
      rowEl.children[col].style.textAlign = "center"
      rowEl.children[col].appendChild(itag);
    } else if (string.toLowerCase() === 'fail') {
      itag.className = 'fas fa-times';
      rowEl.children[col].innerHTML = null;
      rowEl.children[col].style.textAlign = "center"
      rowEl.children[col].appendChild(itag);
    } else {
      console.log(`pass/fail not in column ${col}`)
    }
  }
  return rowEl;
}

function linkifyFromArray(tag, linkArray) {
  if (Object.prototype.toString.call(linkArray) === '[object String]') {
    return linkifyFromString(tag, linkArray);
  }
  let linkText = '';
  for (link of linkArray) {
    linkText = `${linkText}${link}<br>`; // Append link
  }

  return linkifyFromString(tag, linkText.substr(0, linkText.length-4)); // Remove last <br>
}

function linkifyFromString(tag, htmlText) {
  tag.innerHTML = null;
  tag.innerHTML = htmlText;
  let anchors = tag.getElementsByTagName('a');
  if (anchors.length > 0) {
    for (let a of anchors) {
      a.className = 'stmt-dblink';
      a.target = "_blank"
    }
  }
  return tag;
}

function countPasses(results, mts) {
  let count = 0;
  for (mt of mts) {
    if (results[mt][0].toLowerCase() === 'pass') {count++};
  }
  return count;
};

function toTitleCase(phrase) {
  let newPhrase = phrase.split('_');
  newPhrase = newPhrase.map(word => word.charAt(0).toUpperCase() + word.slice(1));
  newPhrase = newPhrase.join(' ');
  return newPhrase;
};

// Populate model and test stats jsons to modelTestResultBody
function populateTestResultTable(tableBody, model_json, test_json) {

  // IDs
  let stmtTypDistId = '#modelTestResultBody';
  let pasRatId = '#passedRatio';
  let pasAppId = '#passedApplied';
  let agDist = '#agentDistr';
  let stmtTime = '#stmtsOverTime';
  let sources = '#sourceDistr';

  // Dates
  model_dates = model_json.changes_over_time.dates;
  model_dates.unshift('x');
  test_dates = test_json.changes_over_time.dates;
  test_dates.unshift('x');

  let all_model_types = ['pysb', 'pybel', 'signed_graph', 'unsigned_graph']
  let current_model_types = [];
  let cols = [];
  let count = 0;
  for (mt of all_model_types) {if (mt in test_json.test_round_summary) {
    current_model_types.push(mt)
    count++
    cols.push(count)}};

  //  Model Tab

  // Stmt type distribution bar graph 
  let stmt_type_array = [];
  let stmt_freq_array = ['Statements count'];

  for (let pair of model_json.model_summary.stmts_type_distr) {
    stmt_type_array.push(pair[0]);
    stmt_freq_array.push(pair[1])
  }
  // See example at: https://c3js.org/samples/axes_x_tick_format.html
  stmtTypeDataParams = {
    // x: 'x',
    columns: [
      stmt_freq_array
    ],
    type: 'bar'
  };

  let stmtTypeChart = generateBar(stmtTypDistId, stmtTypeDataParams, stmt_type_array, '');

  // Top agents bar graph
  let top_agents_array = [];
  let agent_freq_array = ['Agent count'];

  for (let pair of model_json.model_summary.agent_distr.slice(0, 10)) {
    top_agents_array.push(pair[0]);
    agent_freq_array.push(pair[1])
  }

  let agentDataParams = {
    columns: [
      agent_freq_array
    ],
    type: 'bar'
  };

  let agentChart = generateBar(agDist, agentDataParams, top_agents_array, '');

  var sourceChart = NaN;
  if (model_json.model_summary.sources) {
    // Source APIs bar graph
    let sources_array = [];
    let source_freq_array = ['Evidence count']

    for (let pair of model_json.model_summary.sources) {
      sources_array.push(pair[0]);
      source_freq_array.push(pair[1]);
    }

    let sourceDataParams = {
      columns: [
        source_freq_array
      ],
      type: 'bar'
    };

    var sourceChart = generateBar(sources, sourceDataParams, sources_array, '');
  }
  // Statements over Time line graph
  let stmtsOverTime = model_json.changes_over_time.number_of_statements;
  stmtsOverTime.unshift('Statements');

  let stmtsCountDataParams = {
    x: 'x',
    xFormat: '%Y-%m-%d-%H-%M-%S',
    columns: [
      model_dates,
      stmtsOverTime
    ],
    onclick: redirectToPast
  };

  let stmtsCountChart = generateLineArea(stmtTime, stmtsCountDataParams, '');

  // Tests Tab

  // Passed ratio line graph
  let passedRatioColumns = [test_dates]

  for (mt of current_model_types) {
    let mt_changes = test_json.changes_over_time[mt]
    let passedRatio = mt_changes.passed_ratio
    passedRatio = passedRatio.map(function(element) {
      return (element*100).toFixed(2);
    })
    var i
    let dif = test_dates.length - passedRatio.length
    for (i = 1; i < dif; i++) {passedRatio.unshift(null)}
    passedRatio.unshift(FORMATTED_MODEL_NAMES[mt]);
    passedRatioColumns.push(passedRatio)
  };

  lineDataParams = {
    x: 'x',
    xFormat: '%Y-%m-%d-%H-%M-%S',
    columns: passedRatioColumns,
    onclick: redirectToPast
  };

  let lineChart = generateLineArea(pasRatId, lineDataParams, '');

  // Applied/passed area graph
  let appliedTests = test_json.changes_over_time.number_applied_tests;
  appliedTests.unshift('Applied Tests');
  let appliedPassedColumns = [test_dates];

  for (mt of current_model_types) {
    let mt_changes = test_json.changes_over_time[mt];
    let passedTests = mt_changes.number_passed_tests;
    let i;
    let dif = test_dates.length - passedTests.length;
    for (i = 1; i < dif; i++) {passedTests.unshift(null)}
    passedTests.unshift(`${FORMATTED_MODEL_NAMES[mt]} Passed Tests`);
    appliedPassedColumns.push(passedTests)
  }

  appliedPassedColumns.push(appliedTests);

  let passedAppliedParams = {
    x: 'x',
    xFormat: '%Y-%m-%d-%H-%M-%S',
    columns: appliedPassedColumns,
    type: 'area',
    onclick: redirectToPast
  };

  let areaChart = generateLineArea(pasAppId, passedAppliedParams, '');


  // Force redraw of charts to prevent chart overflow
  // https://c3js.org/reference.html#api-flush
  $('a[data-toggle=tab]').on('shown.bs.tab', function() { // This will trigger when tab is clicked
    stmtTypeChart.flush();
    agentChart.flush();
    sourceChart.flush();
    stmtsCountChart.flush();
    lineChart.flush();
    areaChart.flush();
  });
  $(function() {
    //Executed on page load with URL containing an anchor tag.
    if($(location.href.split("#")[1])) {
        var target = $('#'+location.href.split("#")[1]);
        if (target.length) {
          $('html,body').animate({
            scrollTop: target.offset().top - 70 //offset height of header here too.
          }, 1000);
          return false;
        }
      }
  });
}

/* c3 chart functions
Found here:

https://c3js.org/
*/

function generateBar(chartDivId, dataParams, ticksLabels, chartTitle) {
  return c3.generate({
    bindto: chartDivId,
    data: dataParams,
    bar:  {
      width: {
        ratio: 0.5 // this makes bar width 50% of length between ticks
      }
    },
    axis: {
      rotated: true,
      x: {
          type: 'category',
          categories: ticksLabels
      }
    },
    title: {
      text: chartTitle
    }
  });
}

function generateLineArea(chartDivId, dataParams, chartTitle) {
  return c3.generate({
    bindto: chartDivId,
    data: dataParams,
    axis: {
      x: {
        type: 'timeseries',
        tick: {
          rotate: -45,
          format: '%Y-%m-%d-%H-%M-%S'
        }
      },
      y: {
        min: 0,
        max: null,
        padding: 0
      }
    },
    title: {
      text: chartTitle
    },
    zoom: {
      enabled: true
    }
  });
}
