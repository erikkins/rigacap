-- SqlProcedure: [dbo].[getNewSells]

set nocount on

	declare @startdate datetime
	select @startdate = AtWhenSubscribe
	from Member where MemberID=@MemberID

	if @startdate < @atwhen
		begin
			select s.stockID, s.ticker, s.companyname, sd.price, Convert(int,Round(((Convert(decimal(5,2),sd.price) * 100)/sdb.price)-100,0)) as PercentChange, ss.comment
			from stockbuy sb
			inner join stock s on s.stockID=sb.StockID
			inner join stocksell ss on ss.buyID=sb.buyID
			inner join stockdata sd on s.stockID=sd.stockID and sd.atwhen=ss.atwhen
			inner join stockdata sdb on s.stockID=sdb.stockID and sdb.atwhen=sb.atwhen
			where ss.atwhen = @atwhen
			and sb.channel='S'
			order by s.companyname
		end
	else
		begin
			select null as StockID, '' as Ticker,'' as CompanyName, 0 as price, 0 as PercentChange, '' as Comment
		end
set nocount off
