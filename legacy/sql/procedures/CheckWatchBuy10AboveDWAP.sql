-- SqlProcedure: [dbo].[CheckWatchBuy10AboveDWAP]

--this is a buy watch, but we're not using the startdate ever...
declare @dwapdate datetime

declare @watchID int
declare @ticker varchar(5)

declare @buyID int

declare @dwapprice money, @currprice money, @avg float, @buydate datetime, @lastDataDate datetime
declare @yesterday datetime
select @yesterday = dateadd(day,-1,getdate())

select @dwapdate = lastdwapdate
from stock
where stockID=@stockID
		
			--don't buy if already bought
			if not exists (select * from stockbuy where stockID = @stockID and Status=0 and Channel ='D')
				begin							
					--select @newhighdate = convert(char(4),datepart(year, atwhen)) + '-' + right('00' + convert(varchar(2),datepart(month, atwhen)),2) + '-'+ right('00' + convert(varchar(2), datepart(day, atwhen)),2)
					select @dwapprice = price
					from stockData
					where StockID = @StockID
					and AtWhen = @dwapdate
					and price > 46
					and Volume > 1000000

					if @dwapprice is null
						begin
							Print 'DWAP Price is null'
							return
						end

					select @currprice = LastPrice, @avg = LastVolume, @lastDataDate = LastDataDate, @ticker = ticker 
					from Stock
					where StockID = @StockID

					
					--if there was a split after the dwapdate and it was applied, we need to account for that
					declare @revsplitmult decimal(3,2), @splitdate datetime
					select @revsplitmult= 1.0
					declare @split varchar(50)					
					declare @left int, @right int, @colloc int

					if exists (select * from stocksplit where stockID=@stockID and atwhen > @dwapdate and applydate is not null)
					begin
						select @splitdate = atwhen, @split=split from stocksplit where stockID=@stockID and atwhen > @dwapdate and applydate is not null
						select @colloc = charindex(':', @split)
						select @left = substring(@split, 1, @colloc -1), @right = substring(@split, @colloc+1, len(@split)-@colloc+1)
						--note that this is reverse from the apply split, since we are UNAPPLYING the split here
						select @revsplitmult = convert(decimal,@left)/@right												
					end

					select top 1 @buydate = atwhen
					from StockData
					where stockID = @stockID
					and atwhen > @dwapdate
					and Price * @revsplitmult > @dwapprice * 1.10
					and Price * @revsplitmult > 50
					and Volume > 1000000
					order by atwhen asc

					if @buydate is null
						begin
							Print 'BUYDATE is NULL'
							return							
						end

					if @splitdate is null
						begin
							--trick the logic
							select @splitdate = @buydate
						end


					select @currprice = Price * @revsplitmult
					from StockData where atwhen = @buydate
					and StockID = @stockID										

					select @avg = avg(Volume)
					from StockData 
					where atwhen between @dwapdate and @buydate
					and StockID = @stockID

					if @currprice > 50
						begin
							if @currprice >= @dwapprice * 1.10
								begin
									if @avg > 1000000
										begin											
											declare @comment varchar(1000)
											select @comment =  'Price exceeded 10% above DWAP Price at > 1M volume on ' + convert(varchar(14),@buydate,101)											
											print @comment				
										end
									else
										begin							
											Print @ticker + ' would have been purchased at 10% above DWAP, but volume did not exceed 1M'																		
										end
								end
						end
				end
