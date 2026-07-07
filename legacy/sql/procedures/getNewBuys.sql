-- SqlProcedure: [dbo].[getNewBuys]

set nocount on

	declare @startdate datetime
	select @startdate = AtWhenSubscribe
	from Member where MemberID=@MemberID

	if @startdate < @atwhen
		begin
			select s.stockID, s.ticker, s.companyname, sd.price
			from stockbuy sb
			inner join stock s on s.stockID=sb.StockID
			inner join stockdata sd on s.stockID=sd.stockID and sd.atwhen=sb.atwhen
			where sb.atwhen = @atwhen
			and sb.channel='S'
			order by s.companyname
		end
	else
		begin
			select null as StockID, '' as Ticker,'' as CompanyName, 0 as Price
		end
set nocount off
