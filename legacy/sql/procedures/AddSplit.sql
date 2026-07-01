-- SqlProcedure: [dbo].[AddSplit]

set nocount on

/*
declare @msg varchar(200)
select @msg = convert(varchar,@ratio)

exec saveAudit @atwhen, @msg , @stockID, 'SPLIT', 'I'
*/
if not exists (select * from stocksplit where stockID = @stockID and atwhen = @Atwhen)
	begin
		insert into StockSplit (stockID, atwhen, split)
			select @stockID, @atwhen, @ratio
	end

select @@rowcount
--need to update ALL buys for that stock that are active
/*
declare @left int, @right int, @colloc int
select @colloc = charindex(':', @ratio)
select @left = substring(@ratio, 1, @colloc -1), @right = substring(@ratio, @colloc+1, len(@ratio)-@colloc+1)

update stockbuy
set shares = shares * Convert(decimal,@left)/@right
where stockID = @stockID
and status = 0
and atwhen > @atwhen
*/

set nocount off
