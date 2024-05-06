const functions = require('@google-cloud/functions-framework');

functions.http('regdata', (req, res) => {

  var json_obj = req.body;
  var insert_obj = {
    insertId: json_obj.DATETIME,
    json: json_obj
  };
  const options = {
  raw: true
  };
  //----------------------------
  // insert
  //----------------------------
  const {BigQuery} = require('@google-cloud/bigquery');
  const bigquery = new BigQuery({ projectId: 'electric-238022' });
  
  var table_name = 'TBL_'+json_obj.TYPE;
  
  console.log(table_name);
  console.log(insert_obj);

  bigquery
    .dataset('DATASET')
    .table(table_name)
    .insert(insert_obj, options)

  .then(function(result) {

    console.log('BQ INSERTED');
    return 'BQ INSERTED';
  })
  .catch((err) => {
    console.error('BQ ERROR : ', err);
    throw new Error(err);
  });

  res.send(`OK`);
});
