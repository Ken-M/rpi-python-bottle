const functions = require('@google-cloud/functions-framework');
const {BigQuery} = require('@google-cloud/bigquery');

const bigquery = new BigQuery({ projectId: 'electric-238022' });

functions.http('regdata', async (req, res) => {

  const json_obj = req.body;
  const insert_obj = {
    insertId: json_obj.DATETIME,
    json: json_obj
  };
  const options = {
    raw: true
  };

  const table_name = 'TBL_' + json_obj.TYPE;

  console.log(table_name);
  console.log(insert_obj);

  //----------------------------
  // insert
  //----------------------------
  try {
    await bigquery
      .dataset('DATASET')
      .table(table_name)
      .insert(insert_obj, options);

    console.log('BQ INSERTED');
    res.send('OK');
  } catch (err) {
    // 500 を返すと送信側（get-power.py）がリトライし、失敗時は再送キューに積まれる
    console.error('BQ ERROR : ', err);
    res.status(500).send('BQ ERROR');
  }
});
